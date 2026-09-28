"""Planificador: puerta horaria, idempotencia y presupuesto del Brief; alertas por materialidad (scheduler.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from atlas_core import scheduler as sch
from atlas_core.db import dumps, now_iso

PROFILE = {"usuario": {"hora_brief": "07:00", "zona_horaria": "UTC"}}


def _clock(h: int, m: int):
    class FakeDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 28, h, m, tzinfo=tz)

    return FakeDT


def _events(db, n: int, materiality: float = 50, prefix: str = "e", at: str | None = None):
    ts = at or now_iso()
    for i in range(n):
        db.exec(
            "INSERT INTO event(id,title_neutral,countries,first_seen_at,last_update_at,n_docs,materiality) "
            "VALUES (?,?,?,?,?,1,?)",
            (f"{prefix}{i}", f"Evento {i}", dumps(["ES"]), ts, ts, materiality),
        )


def _no_llm(monkeypatch):
    monkeypatch.setattr(sch.settings, "anthropic_api_key", None)  # sin redact_brief ni gasto
    monkeypatch.setattr(sch, "profile_config", lambda: PROFILE)  # no depende de config/perfil.yaml


async def test_maybe_brief_is_time_gated_and_idempotent(db, monkeypatch):
    _no_llm(monkeypatch)
    _events(db, 5)
    s = sch.Scheduler(db)
    monkeypatch.setattr(sch, "datetime", _clock(6, 30))
    await s._maybe_brief()
    assert db.scalar("SELECT COUNT(*) FROM brief") == 0
    monkeypatch.setattr(sch, "datetime", _clock(7, 5))
    await s._maybe_brief()
    assert sorted(r["kind"] for r in db.all("SELECT kind FROM brief")) == ["executive", "study"]
    assert db.scalar("SELECT COUNT(*) FROM alert WHERE kind = 'brief'") == 1
    await s._maybe_brief()  # misma fecha: no duplica (clave brief.date + kind='study')
    assert db.scalar("SELECT COUNT(*) FROM brief") == 2
    assert db.scalar("SELECT COUNT(*) FROM alert") == 1


async def test_maybe_brief_generates_at_exact_hour(db, monkeypatch):
    """A la hora configurada exacta ya genera: detecta la mutación '<' -> '<='."""
    _no_llm(monkeypatch)
    _events(db, 5)
    monkeypatch.setattr(sch, "datetime", _clock(7, 0))
    await sch.Scheduler(db)._maybe_brief()
    assert db.scalar("SELECT COUNT(*) FROM brief") == 2


async def test_maybe_brief_needs_five_recent_events(db, monkeypatch):
    _no_llm(monkeypatch)
    _events(db, 4)
    monkeypatch.setattr(sch, "datetime", _clock(7, 5))
    await sch.Scheduler(db)._maybe_brief()
    assert db.scalar("SELECT COUNT(*) FROM brief") == 0
    assert db.scalar("SELECT COUNT(*) FROM alert") == 0


async def test_maybe_brief_counts_only_the_last_24_hours(db, monkeypatch):
    """Umbral ISO: 4 eventos de hace 25 h no cuentan aunque caigan en el mismo día natural."""
    _no_llm(monkeypatch)
    old = (datetime.now(UTC) - timedelta(hours=25)).replace(microsecond=0).isoformat()
    _events(db, 4, prefix="old", at=old)
    _events(db, 4, prefix="new")
    monkeypatch.setattr(sch, "datetime", _clock(7, 5))
    await sch.Scheduler(db)._maybe_brief()
    assert db.scalar("SELECT COUNT(*) FROM brief") == 0


async def test_maybe_brief_calls_the_llm_editor_once(db, monkeypatch):
    """Con clave, redact_brief se llama una sola vez por día (nunca en cada pasada de 15 min)."""
    _no_llm(monkeypatch)
    monkeypatch.setattr(sch.settings, "anthropic_api_key", "x")
    calls: list[str] = []
    monkeypatch.setattr("atlas_core.agents.redact_brief", lambda db_, brief_id: calls.append(brief_id))
    _events(db, 5)
    monkeypatch.setattr(sch, "datetime", _clock(7, 5))
    s = sch.Scheduler(db)
    await s._maybe_brief()
    await s._maybe_brief()
    assert len(calls) == 1 and db.one("SELECT id FROM brief WHERE kind = 'study'")["id"] == calls[0]


async def test_alerts_only_above_push_threshold_and_once(db):
    _events(db, 1, materiality=85, prefix="hi")
    _events(db, 1, materiality=60, prefix="lo")  # bajo el umbral push_alert (80)
    s = sch.Scheduler(db)
    await s._alerts()
    rows = db.all("SELECT kind, json_extract(ref, '$.event_id') AS event_id FROM alert")
    assert [(r["kind"], r["event_id"]) for r in rows] == [("materiality", "hi0")]
    await s._alerts()  # deduplica por ref.event_id
    assert db.scalar("SELECT COUNT(*) FROM alert") == 1


async def test_alerts_window_is_24_hours_not_the_calendar_day(db):
    old = (datetime.now(UTC) - timedelta(hours=25)).replace(microsecond=0).isoformat()
    _events(db, 1, materiality=90, prefix="old", at=old)
    _events(db, 1, materiality=90, prefix="new")
    await sch.Scheduler(db)._alerts()
    assert [r[0] for r in db.all("SELECT json_extract(ref, '$.event_id') FROM alert")] == ["new0"]
