"""Capa LLM con un cliente falso que devuelve `Message` reales del SDK: stop_reason (refusal, max_tokens),
uso real en llm_call aunque la salida no sirva, reintentos, streams abandonados y el brief crítico."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from anthropic.types import Message, TextBlock
from anthropic.types import Usage as SDKUsage
from anthropic.types.refusal_stop_details import RefusalStopDetails

from atlas_core import agents
from atlas_core.agents import ExtractorOutput, RedTeamReport
from atlas_core.llm import LLM, LLMRefused, LLMTruncated

TRUNCATED_JSON = '{"entities": [], "claims": [{"text_es": "x"'
VALID_JSON = '{"entities": [], "claims": []}'


def msg(
    text: str | None,
    stop: str = "end_turn",
    category: str | None = None,
    explanation: str | None = None,
    inp: int = 9000,
    out: int = 100,
) -> Message:
    details = (
        RefusalStopDetails(type="refusal", category=category, explanation=explanation)
        if stop == "refusal"
        else None
    )
    return Message(
        id="msg_test",
        content=[TextBlock(type="text", text=text)] if text is not None else [],
        model="claude-test",
        role="assistant",
        stop_reason=stop,  # type: ignore[arg-type]
        stop_details=details,
        type="message",
        usage=SDKUsage(input_tokens=inp, output_tokens=out),
    )


class FakeStream:
    """Imita `MessageStream`: text_stream, get_final_message, current_message_snapshot y cierre por `with`."""

    def __init__(self, chunks: list[str], final: Message):
        self.chunks, self.final = chunks, final
        self.started = False
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True
        return False

    @property
    def text_stream(self):
        for c in self.chunks:
            self.started = True
            yield c

    def get_final_message(self) -> Message:
        return self.final

    @property
    def current_message_snapshot(self) -> Message:
        if not self.started:
            raise AssertionError("sin message_start")  # como el SDK
        # el snapshot de message_start trae la entrada real y ~1 token de salida
        return msg("", stop="end_turn", inp=self.final.usage.input_tokens, out=1)


class FakeMessages:
    def __init__(self, responses=(), streams=()):
        self.responses = list(responses)
        self.streams = list(streams)
        self.calls: list[dict] = []
        self.stream_calls: list[dict] = []

    def create(self, **kw):
        self.calls.append(kw)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def stream(self, **kw):
        self.stream_calls.append(kw)
        return self.streams.pop(0)


@pytest.fixture()
def make_llm(db, monkeypatch):
    from atlas_core import llm as llm_mod

    monkeypatch.setattr(llm_mod.settings, "anthropic_api_key", "test-key")

    def _make(**kw) -> LLM:
        llm = LLM(db)
        llm._client = SimpleNamespace(messages=FakeMessages(**kw))
        monkeypatch.setattr(agents, "get_llm", lambda _db: llm)
        return llm

    yield _make
    llm_mod._llm = None


def rows(db) -> list[dict]:
    return [dict(r) for r in db.all("SELECT * FROM llm_call ORDER BY id")]


# ---------- complete() ----------


def test_truncated_json_is_retried_with_more_max_tokens_and_real_usage_is_logged(db, make_llm):
    llm = make_llm(
        responses=[
            msg(TRUNCATED_JSON, stop="max_tokens", inp=9000, out=8192),
            msg(VALID_JSON, stop="end_turn", inp=9100, out=40),
        ]
    )
    res = llm.complete("synthesis", "equipo_rojo", "x", module="event_analysis", schema=ExtractorOutput)
    calls = llm._client.messages.calls
    assert len(calls) == 2
    assert calls[0]["max_tokens"] == 8192 and calls[1]["max_tokens"] == 16000  # el doble, con tope
    # mismo prompt: sin turno assistant fabricado
    assert calls[0]["messages"] == calls[1]["messages"] == [{"role": "user", "content": "x"}]
    assert calls[0]["output_config"]["format"]["type"] == "json_schema"  # parámetro canónico
    assert calls[0]["output_config"]["effort"] == "medium" and calls[0]["thinking"] == {"type": "adaptive"}
    r = rows(db)
    assert len(r) == 2
    assert r[0]["ok"] == 0 and r[0]["error"] == "max_tokens"
    assert r[0]["input_tokens"] == 9000 and r[0]["output_tokens"] == 8192 and r[0]["cost_usd"] > 0
    assert json.loads(r[0]["meta"]) == {"stop_reason": "max_tokens", "max_tokens": 8192}
    assert r[1]["ok"] == 1 and json.loads(r[1]["meta"])["stop_reason"] == "end_turn"
    assert res.parsed is not None and res.parsed.claims == [] and res.call_id == r[1]["id"]
    assert llm.spent_today() == pytest.approx(
        r[0]["cost_usd"] + r[1]["cost_usd"]
    )  # el tope diario lo ve todo


def test_truncated_twice_raises_llm_truncated_after_one_retry(db, make_llm):
    llm = make_llm(responses=[msg(TRUNCATED_JSON, stop="max_tokens"), msg(TRUNCATED_JSON, stop="max_tokens")])
    with pytest.raises(LLMTruncated):
        llm.complete("bulk", "extractor", "x", module="ingest", schema=ExtractorOutput)
    assert len(llm._client.messages.calls) == 2
    assert [r["ok"] for r in rows(db)] == [0, 0] and all(r["input_tokens"] == 9000 for r in rows(db))


def test_refusal_is_logged_with_real_usage_and_never_retried(db, make_llm):
    llm = make_llm(responses=[msg(None, stop="refusal", category="cyber", explanation="no", inp=9000, out=1)])
    with pytest.raises(LLMRefused) as ei:
        llm.complete("synthesis", "equipo_rojo", "x", module="event_analysis", schema=RedTeamReport)
    assert ei.value.category == "cyber" and "cyber" in str(ei.value)
    assert len(llm._client.messages.calls) == 1  # exactamente una llamada: nada de reenviar el prompt
    r = rows(db)
    assert len(r) == 1
    assert r[0]["ok"] == 0 and r[0]["error"] == "refusal: cyber"
    assert r[0]["input_tokens"] == 9000 and r[0]["cost_usd"] > 0
    meta = json.loads(r[0]["meta"])
    assert meta["stop_reason"] == "refusal" and meta["refusal_category"] == "cyber"


def test_empty_text_without_schema_is_an_error_not_a_success(db, make_llm):
    llm = make_llm(responses=[msg(None, stop="end_turn")])
    with pytest.raises(ValueError):
        llm.complete("synthesis", "editor_jefe", "x", module="brief")
    r = rows(db)
    assert len(r) == 1 and r[0]["ok"] == 0 and r[0]["error"] == "empty" and r[0]["input_tokens"] == 9000


def test_schema_error_still_retries_with_the_validation_error(db, make_llm):
    llm = make_llm(responses=[msg('{"entities": "nope"}'), msg(VALID_JSON)])
    res = llm.complete("bulk", "extractor", "x", module="ingest", schema=ExtractorOutput)
    calls = llm._client.messages.calls
    assert len(calls) == 2 and res.parsed is not None
    assert [m["role"] for m in calls[1]["messages"]] == ["user", "assistant", "user"]
    assert "no valida contra el esquema" in calls[1]["messages"][2]["content"]
    r = rows(db)
    assert r[0]["ok"] == 0 and r[0]["error"].startswith("schema:") and r[0]["input_tokens"] == 9000
    assert r[1]["ok"] == 1


def test_api_exception_is_logged_and_reraised(db, make_llm):
    llm = make_llm(responses=[RuntimeError("boom")])
    with pytest.raises(RuntimeError):
        llm.complete("bulk", "extractor", "x", module="ingest")
    r = rows(db)
    assert len(r) == 1 and r[0]["ok"] == 0 and r[0]["error"] == "RuntimeError: boom"


# ---------- stream() / stream_agent ----------


def test_stream_agent_refusal_emits_error_and_marks_run_error(db, make_llm):
    llm = make_llm(streams=[FakeStream([], msg(None, stop="refusal", category="bio", inp=5000, out=1))])
    events = list(agents.stream_agent(db, "deepen", "editor_jefe", "synthesis", "hola", ref="e1"))
    assert [e["type"] for e in events] == ["start", "error"]
    assert events[1]["category"] == "bio" and "bio" in events[1]["message"]
    run = db.one("SELECT status, output FROM agent_run")
    assert run["status"] == "error" and json.loads(run["output"])["refusal_category"] == "bio"
    r = rows(db)
    assert (
        len(r) == 1 and r[0]["ok"] == 0 and r[0]["error"] == "refusal: bio" and r[0]["input_tokens"] == 5000
    )
    assert len(llm._client.messages.stream_calls) == 1


def test_stream_done_exposes_stop_reason_and_truncation(db, make_llm):
    make_llm(streams=[FakeStream(["ho", "la"], msg("hola", stop="max_tokens", inp=100, out=8192))])
    events = list(agents.stream_agent(db, "deepen", "editor_jefe", "synthesis", "hola", ref="e1"))
    done = events[-1]
    assert done["type"] == "done" and done["text"] == "hola"
    assert done["stop_reason"] == "max_tokens" and done["truncated"] is True
    run = db.one("SELECT status, output FROM agent_run")
    assert run["status"] == "done" and json.loads(run["output"])["truncated"] is True
    r = rows(db)
    assert r[0]["ok"] == 1 and json.loads(r[0]["meta"])["stop_reason"] == "max_tokens"


def test_abandoned_stream_is_logged_with_estimate_and_run_is_aborted(db, make_llm):
    fs = FakeStream(["a" * 40, "b" * 40, "c" * 40], msg("abc", inp=1200, out=30))
    make_llm(streams=[fs])
    gen = agents.stream_agent(db, "deepen", "editor_jefe", "synthesis", "hola", ref="e1")
    assert next(gen)["type"] == "start"
    assert next(gen)["type"] == "delta"
    gen.close()  # el consumidor SSE se desconecta
    assert fs.closed
    r = rows(db)
    assert len(r) == 1
    assert r[0]["ok"] == 0 and r[0]["error"].startswith("aborted")
    assert r[0]["input_tokens"] == 1200  # del snapshot de message_start
    assert r[0]["output_tokens"] == 10  # 40 caracteres emitidos ≈ 10 tokens, marcado como estimación
    meta = json.loads(r[0]["meta"])
    assert (
        meta["aborted"] is True and meta["output_tokens_estimated"] is True and meta["chars_streamed"] == 40
    )
    run = db.one("SELECT status, output FROM agent_run")
    assert run["status"] == "aborted"
    out = json.loads(run["output"])
    assert out["aborted"] is True and out["partial"] == "a" * 40


def test_abandoned_raw_llm_stream_is_logged(db, make_llm):
    llm = make_llm(streams=[FakeStream(["xyz"], msg("xyz", inp=300, out=3))])
    g = llm.stream("analysis", "analista_regional", "x", module="on_demand")
    assert next(g) == "xyz"
    g.close()
    r = rows(db)
    assert len(r) == 1 and json.loads(r[0]["meta"])["aborted"] is True and r[0]["output_tokens"] == 1


def test_stream_exception_is_logged(db, make_llm):
    class Boom(FakeStream):
        @property
        def text_stream(self):
            raise RuntimeError("caída")
            yield  # pragma: no cover

    make_llm(streams=[Boom([], msg(""))])
    events = list(agents.stream_agent(db, "deepen", "editor_jefe", "synthesis", "hola", ref="e1"))
    assert events[-1]["type"] == "error"
    assert rows(db)[0]["error"] == "RuntimeError: caída"
    assert db.one("SELECT status FROM agent_run")["status"] == "error"


# ---------- redact_brief (crítico, sin supervisión) ----------


def _brief(db) -> str:
    from atlas_core.engines.brief import compose_brief

    return compose_brief(db)["id"]


def test_redact_brief_keeps_rules_on_refusal_and_raises_an_alert(db, make_llm):
    bid = _brief(db)
    make_llm(responses=[msg(None, stop="refusal", category="cyber", inp=7000, out=1)])
    with pytest.raises(LLMRefused):
        agents.redact_brief(db, bid)
    row = db.one("SELECT composed_by, content FROM brief WHERE id = ?", (bid,))
    assert row["composed_by"] == "rules" and "redaction_md" not in json.loads(row["content"])
    alert = db.one("SELECT title, ref FROM alert WHERE kind = 'llm'")
    assert alert is not None and json.loads(alert["ref"])["brief_id"] == bid
    assert rows(db)[0]["error"] == "refusal: cyber"


def test_redact_brief_does_not_claim_llm_provenance_for_unusable_output(db, make_llm):
    bid = _brief(db)
    make_llm(responses=[msg("# parcial", stop="stop_sequence")])
    out = agents.redact_brief(db, bid)
    assert out["composed_by"] == "rules" and "stop_sequence" in out["reason"]
    assert db.one("SELECT composed_by FROM brief WHERE id = ?", (bid,))["composed_by"] == "rules"


def test_redact_brief_persists_llm_on_complete_output(db, make_llm):
    bid = _brief(db)
    make_llm(responses=[msg("# Brief\n\n- hecho [c1]", stop="end_turn")])
    out = agents.redact_brief(db, bid)
    assert out["composed_by"] == "llm" and out["redaction_md"].startswith("# Brief")
    row = db.one("SELECT composed_by, content FROM brief WHERE id = ?", (bid,))
    assert row["composed_by"] == "llm" and json.loads(row["content"])["redaction_md"].startswith("# Brief")


def test_brief_payload_trims_items_before_serializing():
    facts = [{"text": "x" * 300, "claim_id": f"c{i}"} for i in range(3)]
    content = {
        "date": "2026-09-28",
        "redaction_md": "anterior",
        "sections": [
            {"name": "MUNDO", "items": [{"event_id": f"e{i}", "facts": list(facts)} for i in range(40)]}
        ],
    }
    payload = agents._brief_payload(content, limit=6000)
    text = json.dumps(payload, ensure_ascii=False)
    assert len(text) <= 6000 and "anterior" not in text
    json.loads(text)  # JSON íntegro, nunca cortado por la mitad
    assert 0 < len(payload["sections"][0]["items"]) < 40
    assert all(len(it["facts"]) == 1 for it in payload["sections"][0]["items"])
