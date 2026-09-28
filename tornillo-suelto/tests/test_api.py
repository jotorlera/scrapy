"""API: salud, semilla, radar, ciclo completo de pronóstico, notas y mapas argumentales, agentes sin clave,
servicio de la SPA (sin traversal ni eclipse de /api), cotas de parámetros, padres inexistentes, CSRF/Host."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from atlas_core.engines.brief import SOCRATIC
from conftest import make_doc, make_source


@pytest.fixture()
def client(seeded):
    from atlas_core.api.app import app

    # Host local: la app rechaza (400) cualquier otro Host para cortar el DNS rebinding.
    with TestClient(app, base_url="http://127.0.0.1:8765") as c:
        yield c


def test_health_and_seed_counts(client, seeded):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["name"] == "TORNILLO SUELTO"
    assert body["counts"]["sources"] > 150
    assert seeded.scalar("SELECT COUNT(*) FROM historical_case") >= 60
    assert seeded.scalar("SELECT COUNT(*) FROM argument_node") >= 10


def test_radar_and_event_detail_after_processing(client, seeded):
    from atlas_core.pipeline import process_new_documents

    s1 = make_source(seeded, "t_pais", tier=2, country="ES", ideology="center_left")
    s2 = make_source(seeded, "t_abc", tier=2, country="ES", ideology="right")
    s3 = make_source(seeded, "t_guardian", tier=2, country="GB", bloc="anglo", ideology="center_left")
    title = "El Gobierno de España aprueba la ley de vivienda y entra en vigor en enero"
    for s in (s1, s2, s3):
        make_doc(
            seeded,
            s,
            title,
            "La norma limita los alquileres en zonas tensionadas según el Ministerio de Vivienda.",
        )
    st = process_new_documents(seeded, use_llm=False)
    assert st["docs"] == 3
    r = client.get("/api/radar", params={"hours": 24})
    assert r.status_code == 200
    events = r.json()["events"]
    assert events and events[0]["n_sources"] == 3 and "ES" in events[0]["countries"]
    assert events[0]["materiality_breakdown"]["features"]
    eid = events[0]["id"]
    d = client.get(f"/api/events/{eid}").json()
    assert d["claims"] and all(c["evidence"] for c in d["claims"])
    assert all(ev["quote"] for c in d["claims"] for ev in c["evidence"])
    assert d["timeline"] and d["analogs"]["cases"]
    p = client.get(f"/api/events/{eid}/prism").json()
    assert p["matrix"]["cells"] and "ideology" in p["axes"]
    assert client.post(f"/api/events/{eid}/flag", json={"flag": "important"}).json()["ok"]
    assert client.get("/api/search", params={"q": "vivienda"}).json()["events"]


# ───────────── pronósticos ─────────────

Q_TITLE = "¿Aprobará el Congreso los presupuestos antes del 31 de diciembre de 2026?"
Q_CRITERIA = (
    "SÍ si el BOE publica la Ley de Presupuestos Generales del Estado antes del 31-12-2026 (fuente: boe.es)."
)


def _question(client, base_rate: float | None = None, close_at: str = "2026-12-31T00:00:00+00:00") -> str:
    body = {
        "title": Q_TITLE,
        "resolution_criteria": Q_CRITERIA,
        "resolution_source": "BOE",
        "close_at": close_at,
    }
    if base_rate is not None:
        body |= {"base_rate": base_rate, "base_rate_note": "frecuencia histórica de aprobación en plazo"}
    r = client.post("/api/forecasts", json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_forecast_full_cycle_user_before_system(client):
    r = client.post(
        "/api/forecasts",
        json={"title": "corto", "resolution_criteria": "x", "close_at": "2027-01-01T00:00:00+00:00"},
    )
    assert r.status_code == 422
    qid = _question(client, base_rate=0.45)
    q = client.get(f"/api/forecasts/{qid}").json()
    assert q["latest"]["base_rate"]["p"] == 0.45
    r = client.post(
        f"/api/forecasts/{qid}/forecast", json={"probability": 0.7, "rationale": "mayoría estable"}
    )
    assert r.json()["system_probability"] == 0.45
    r = client.post(f"/api/forecasts/{qid}/resolve", json={"outcome": 1})
    scores = r.json()["scores"]
    assert scores["user"]["brier"] == pytest.approx(0.09) and scores["base_rate"]["brier"] == pytest.approx(
        0.3025
    )
    assert r.json()["ignored_after_close"] == []
    cal = client.get("/api/forecasts/calibration", params={"forecaster": "user"}).json()
    assert cal["calibration"]["n"] == 1 and cal["calibration"]["brier"] == pytest.approx(0.09)
    user = next(s for s in cal["summary"] if s["forecaster"] == "user")
    assert user["bss_vs_base_rate"] > 0 and user["n_paired_base_rate"] == 1 and user["bss_vs_market"] == {}
    # una segunda resolución (doble clic, reenvío con el otro botón) no reescribe la historia
    r2 = client.post(f"/api/forecasts/{qid}/resolve", json={"outcome": 0, "note": "contradice"})
    assert r2.status_code == 409
    q = client.get(f"/api/forecasts/{qid}").json()
    assert q["status"] == "resolved" and q["outcome"]["value"] == 1
    assert [s["brier"] for s in q["scores"] if s["forecaster"] == "user"] == [pytest.approx(0.09)]
    cal = client.get("/api/forecasts/calibration", params={"forecaster": "user"}).json()
    assert cal["calibration"]["brier"] == pytest.approx(0.09)
    assert client.post(f"/api/forecasts/{qid}/forecast", json={"probability": 0.5}).status_code == 400


def test_bss_is_paired_by_question(client):
    # Q1: tasa base 0,5 y usuario 0,5 (Brier iguales → BSS emparejado 0). Q2: sin tasa base, usuario 0,99.
    q1 = _question(client, base_rate=0.5)
    client.post(f"/api/forecasts/{q1}/forecast", json={"probability": 0.5})
    assert client.post(f"/api/forecasts/{q1}/resolve", json={"outcome": 1}).status_code == 200
    q2 = _question(client)
    client.post(f"/api/forecasts/{q2}/forecast", json={"probability": 0.99})
    assert client.post(f"/api/forecasts/{q2}/resolve", json={"outcome": 1}).status_code == 200
    cal = client.get("/api/forecasts/calibration", params={"forecaster": "user"}).json()
    user = next(s for s in cal["summary"] if s["forecaster"] == "user")
    assert user["n"] == 2 and user["brier"] == pytest.approx(0.12505)
    # con medias globales saldría 1 − 0,12505/0,25 ≈ 0,5 sin haber batido la tasa base en ninguna pregunta
    assert user["bss_vs_base_rate"] == 0.0 and user["n_paired_base_rate"] == 1


def test_forecast_close_at_guards(client, seeded):
    from atlas_core.db import dumps, new_id

    r = client.post(
        "/api/forecasts",
        json={"title": Q_TITLE, "resolution_criteria": Q_CRITERIA, "close_at": "2025-12-31T00:00:00.000Z"},
    )
    assert r.status_code == 422 and any("futura" in i for i in r.json()["detail"]["issues"])
    # pregunta ya cerrada (insertada directamente: la API no permite crearla)
    qid = new_id()
    seeded.insert(
        "forecast_question",
        {
            "id": qid,
            "title": Q_TITLE,
            "resolution_criteria": Q_CRITERIA,
            "kind": "binary",
            "open_at": "2025-01-01T00:00:00+00:00",
            "close_at": "2025-12-31T00:00:00.000Z",
            "countries": dumps([]),
            "market_links": dumps([]),
            "status": "open",
            "created_by": "user",
        },
    )
    r = client.post(f"/api/forecasts/{qid}/forecast", json={"probability": 0.99})
    assert r.status_code == 400 and "cerró" in r.json()["detail"]
    for forecaster, p, made_at in (
        ("user", 0.3, "2025-06-01T00:00:00+00:00"),
        ("user", 0.99, "2026-09-28T00:00:00+00:00"),  # tras el cierre: no puntúa
        ("atlas_final", 0.95, "2026-01-02T00:00:00+00:00"),  # solo pronóstico tardío: se descarta
    ):
        seeded.insert(
            "forecast",
            {
                "id": new_id(),
                "question_id": qid,
                "forecaster": forecaster,
                "probability": p,
                "made_at": made_at,
            },
        )
    r = client.post(f"/api/forecasts/{qid}/resolve", json={"outcome": 1})
    assert r.status_code == 200, r.text
    assert set(r.json()["scores"]) == {"user"} and r.json()["scores"]["user"]["brier"] == pytest.approx(0.49)
    assert sorted(x["forecaster"] for x in r.json()["ignored_after_close"]) == ["atlas_final", "user"]
    cal = client.get("/api/forecasts/calibration", params={"forecaster": "user"}).json()
    assert cal["calibration"]["n"] == 1 and cal["calibration"]["brier"] == pytest.approx(0.49)


# ───────────── taller y ágora ─────────────


def test_notes_backlinks_and_cards(client):
    a = client.post(
        "/api/notes",
        json={"title": "Libertad negativa", "body_text": "Berlin distingue dos conceptos. Ver [[Pettit]]."},
    ).json()["id"]
    b = client.post(
        "/api/notes",
        json={
            "title": "Pettit",
            "body_text": "Libertad como no dominación. Relación con [[Libertad negativa]].",
        },
    ).json()["id"]
    n = client.get(f"/api/notes/{a}").json()
    assert n["links"] == ["Pettit"] and any(x["id"] == b for x in n["backlinks"])
    assert client.get(f"/api/notes/{a}/export.md").text.startswith("# Libertad negativa")
    cid = client.post(
        "/api/cards",
        json={"front": "¿Quién formuló la libertad como no dominación?", "back": "Philip Pettit"},
    ).json()["id"]
    assert client.get("/api/cards", params={"due_only": True}).json()["due"] == 1
    r = client.post(f"/api/cards/{cid}/review", json={"rating": 3}).json()
    assert r["state"]["interval"] == 2.0
    assert client.get("/api/cards", params={"due_only": True}).json()["due"] == 0


def test_argument_map_analysis(client):
    maps = client.get("/api/agora/maps").json()["maps"]
    rbu = next(m for m in maps if "Renta básica" in m["title"])
    m = client.get(f"/api/agora/maps/{rbu['id']}").json()
    assert len(m["nodes"]) >= 10 and m["edges"]
    assert isinstance(m["analysis"]["unsupported"], list)
    nid = client.post(
        f"/api/agora/maps/{rbu['id']}/nodes",
        json={"kind": "premise", "text": "Premisa sin apoyo añadida por el usuario"},
    ).json()["id"]
    m2 = client.get(f"/api/agora/maps/{rbu['id']}").json()
    assert any(u["id"] == nid for u in m2["analysis"]["unsupported"])
    assert client.get("/api/agora/genealogy").json()["nodes"]


def test_mutations_on_missing_parents_are_404_and_write_nothing(client, seeded):
    from atlas_core.db import dumps, now_iso

    seeded.insert(
        "prediction_market",
        {
            "id": "polymarket:t1",
            "venue": "polymarket",
            "market_id": "t1",
            "question": "Will it rain?",
            "probability": 0.4,
            "fetched_at": now_iso(),
            "tags": dumps([]),
            "followed": 0,
        },
    )
    counts_sql = {
        "forecast": "SELECT COUNT(*) FROM forecast",
        "argument_node": "SELECT COUNT(*) FROM argument_node",
        "argument_edge": "SELECT COUNT(*) FROM argument_edge",
        "followed": "SELECT COUNT(*) FROM prediction_market WHERE followed = 1",
    }
    before = {k: seeded.scalar(sql) for k, sql in counts_sql.items()}
    calls = [
        ("POST", "/api/forecasts/ghost/link_market", {"market_id": "polymarket:t1"}),
        ("POST", "/api/agora/maps/ghost/nodes", {"kind": "thesis", "text": "huérfano"}),
        ("POST", "/api/agora/maps/ghost/edges", {"src": "nope1", "dst": "nope2", "rel": "supports"}),
        ("POST", "/api/events/ghost/flag", {"flag": "important"}),
        ("PUT", "/api/agora/nodes/ghost", {"text": "x"}),
        ("PUT", "/api/agora/nodes/ghost", {}),
        ("PUT", "/api/notes/ghost", {"body_text": "x"}),
        ("POST", "/api/mando/decisions/ghost/outcome", {"outcome": "en curso"}),
        ("POST", "/api/mando/alerts/ghost/dismiss", None),
        ("POST", "/api/markets/prediction/ghost/follow", None),
    ]
    for method, url, body in calls:
        r = client.request(method, url, json=body)
        assert r.status_code == 404, (method, url, r.status_code, r.text)
    assert {k: seeded.scalar(sql) for k, sql in counts_sql.items()} == before
    # aristas: los dos extremos deben ser nodos del mismo mapa
    rbu = next(m for m in client.get("/api/agora/maps").json()["maps"] if "Renta básica" in m["title"])
    other = client.post("/api/agora/maps", json={"title": "Otro mapa"}).json()["id"]
    foreign = client.post(f"/api/agora/maps/{other}/nodes", json={"kind": "thesis", "text": "ajena"}).json()[
        "id"
    ]
    nodes = client.get(f"/api/agora/maps/{rbu['id']}").json()["nodes"]
    r = client.post(
        f"/api/agora/maps/{rbu['id']}/edges", json={"src": foreign, "dst": nodes[0]["id"], "rel": "supports"}
    )
    assert r.status_code == 400
    r = client.post(
        f"/api/agora/maps/{rbu['id']}/edges",
        json={"src": nodes[1]["id"], "dst": nodes[0]["id"], "rel": "supports"},
    )
    assert r.status_code == 200 and r.json()["id"]
    assert client.post("/api/markets/prediction/polymarket:t1/follow").json()["ok"]
    assert seeded.scalar("SELECT followed FROM prediction_market WHERE id = 'polymarket:t1'") == 1


# ───────────── agentes ─────────────


def test_agents_disabled_without_key(client, monkeypatch):
    from atlas_core import llm as llm_mod

    monkeypatch.setattr(llm_mod.settings, "anthropic_api_key", None)
    llm_mod._llm = None
    st = client.get("/api/agents/status").json()
    assert st["enabled"] is False and "ANTHROPIC_API_KEY" in st["message"]
    assert client.get("/api/agents/deepen/whatever").status_code == 409
    assert client.post("/api/agents/red_team/whatever").status_code == 409


def test_agents_sse_unknown_event_is_404(client, monkeypatch):
    from atlas_core import llm as llm_mod

    monkeypatch.setattr(llm_mod.settings, "anthropic_api_key", "sk-ant-fake")
    llm_mod._llm = None
    try:
        assert client.get("/api/agents/status").json()["enabled"] is True
        for url in (
            "/api/agents/deepen/nope",
            "/api/agents/explain/nope",
            "/api/agents/lens?tradition=kant&event_id=nope",
        ):
            r = client.get(url)
            assert r.status_code == 404 and "evento no encontrado" in r.json()["detail"], url
    finally:
        llm_mod._llm = None  # no contaminar otros tests con el cliente de la clave falsa


# ───────────── sala de máquinas, ajustes, brief ─────────────


def test_machine_room_and_settings(client):
    m = client.get("/api/machine").json()
    assert m["totals"]["sources_total"] > 150 and "budget" in m and m["budget"]["daily_cap_usd"] == 10
    s = client.put("/api/settings", json={"theme": "dark", "cat_enabled": False}).json()
    assert s["theme"] == "dark" and s["cat_enabled"] is False
    assert client.get("/api/settings").json()["theme"] == "dark"
    b = client.post("/api/brief/generate").json()["brief"]
    assert b["composed_by"] == "rules" and b["sections"] == [] and b["n_events_considered"] == 0
    assert b["socratic_prompt"] in SOCRATIC


def test_brief_sections_facts_with_quotes_and_primary_source(client, seeded):
    from atlas_core.pipeline import process_new_documents

    s1 = make_source(seeded, "t_pais", ideology="center_left")
    s2 = make_source(seeded, "t_abc", ideology="right")
    s3 = make_source(seeded, "t_boe", type="institution", tier=1)
    title = "El Gobierno de España aprueba la ley de vivienda y entra en vigor en enero"
    for s in (s1, s2, s3):
        make_doc(
            seeded,
            s,
            title,
            "La norma limita los alquileres en zonas tensionadas según el Ministerio de Vivienda.",
        )
    process_new_documents(seeded, use_llm=False)
    b = client.post("/api/brief/generate").json()["brief"]
    assert b["n_events_considered"] == 1 and [s["name"] for s in b["sections"]] == ["ESPAÑA"]
    it = b["sections"][0]["items"][0]
    # cita o descarta: cada hecho del brief lleva document_id y claim_id, nunca opiniones
    assert it["facts"] and all(
        f["document_id"] and f["claim_id"] and f["level"] != "opinion" for f in it["facts"]
    )
    assert it["primary_source"]["name"] == "T_Boe"
    assert it["course_concept"] == "justicia distributiva" and it["narrative_divergence"].startswith(
        "3 fuentes"
    )
    assert it["why_it_matters"].startswith("Cambio difícil de revertir")
    assert b["socratic_prompt"] in SOCRATIC
    latest = client.get("/api/brief/latest").json()["brief"]
    assert latest["id"] == b["id"] and latest["composed_by"] == "rules"
    ex = client.post("/api/brief/generate", params={"kind": "executive"}).json()["brief"]
    assert ex["kind"] == "executive" and [s["name"] for s in ex["sections"]] == ["ESPAÑA"]
    assert client.get("/api/brief/latest", params={"kind": "executive"}).json()["brief"]["id"] == ex["id"]


def test_machine_triggers_do_not_touch_network(client, seeded, monkeypatch):
    from atlas_core.api import routes_ceo

    called: dict[str, object] = {}

    async def fake_ingest(db, force=False, limit_sources=None, use_llm=None):
        called["ingest"] = {"force": force, "limit": limit_sources}
        return {"ok": True}

    async def fake_markets(db):
        called["markets"] = True
        return {"ok": True}

    monkeypatch.setattr(routes_ceo, "run_ingest", fake_ingest)
    monkeypatch.setattr(routes_ceo, "run_markets", fake_markets)
    assert client.post("/api/machine/ingest", params={"force": True, "limit": 3}).json() == {"started": True}
    assert called["ingest"] == {"force": True, "limit": 3}
    assert client.post("/api/machine/markets").json() == {"started": True} and called["markets"]
    running = client.get("/api/machine/running").json()
    assert running.get("ingest") is False and running.get("markets") is False
    monkeypatch.setitem(routes_ceo._running, "ingest", True)
    assert client.post("/api/machine/ingest").json()["started"] is False
    sid = seeded.one("SELECT id FROM source WHERE active = 1")["id"]
    assert client.post(f"/api/machine/sources/{sid}/toggle").json()["active"] == 0
    assert seeded.one("SELECT active FROM source WHERE id = ?", (sid,))["active"] == 0
    assert client.post("/api/machine/sources/nope/toggle").status_code == 404
    rec = client.post("/api/machine/recompute", params={"hours": 24}).json()
    assert rec["events"] == 0 and rec["consolidated"] == 0


def test_mando_and_diet(client, seeded):
    m = client.get("/api/mando").json()
    assert len(m["businesses"]) == 4
    did = client.post(
        "/api/mando/decisions",
        json={
            "title": "Abrir sede en Andorra",
            "premises": ["fiscalidad estable"],
            "success_probability": 0.6,
            "premortem": "fracasó por falta de talento local",
        },
    ).json()["id"]
    assert client.post(f"/api/mando/decisions/{did}/outcome", json={"outcome": "en curso"}).json()["ok"]
    assert client.post("/api/diet/log", json={"action": "open", "seconds": 120, "topic": "Migración"}).json()[
        "ok"
    ]
    rep = client.get("/api/diet/report").json()
    assert rep["n_logs"] == 1 and set(rep["entropy"]) == {"ideology", "bloc", "lang", "type"}
    assert all(v == 0.0 for v in rep["entropy"].values()) and rep["diversity_index"] == 0.0
    s1 = make_source(seeded, "t_izq", ideology="left")
    s2 = make_source(seeded, "t_der", ideology="right")
    d1 = make_doc(seeded, s1, "A")
    d2 = make_doc(seeded, s2, "B")
    for did_ in (d1, d2):
        client.post(
            "/api/diet/log",
            json={"action": "read", "seconds": 120, "document_id": did_, "topic": "Migración"},
        )
    rep = client.get("/api/diet/report").json()
    assert rep["n_logs"] == 3 and rep["entropy"]["ideology"] == 1.0 and rep["diversity_index"] > 0


# ───────────── cotas de parámetros ─────────────


@pytest.mark.parametrize(
    "path",
    [
        "/api/events?limit=-1",
        "/api/events?limit=0",
        "/api/events?offset=-1",
        "/api/events?limit=99999999999999999999",  # antes 500 (OverflowError), ahora 422
        "/api/events?hours=0",
        "/api/radar?limit=-1",
        "/api/primaries?limit=-1",
        "/api/search?q=x&limit=-1",
        "/api/countries/ES?days=-5",
        "/api/actors?limit=-1",
        "/api/archive/analogs?q=x&n=0",
        "/api/diet/report?days=0",
        "/api/agents/runs?limit=-1",
    ],
)
def test_paging_and_window_params_are_bounded(client, path):
    assert client.get(path).status_code == 422


def test_ui_maxima_still_accepted(client):
    # máximos reales de apps/web: no apretar las cotas por debajo
    assert client.get("/api/primaries", params={"hours": 24 * 365, "limit": 200}).status_code == 200
    assert client.get("/api/events", params={"hours": 720, "limit": 300}).status_code == 200
    assert client.get("/api/diet/report", params={"days": 90}).status_code == 200
    assert client.post("/api/machine/recompute", params={"hours": 0}).status_code == 422
    assert client.post("/api/machine/ingest", params={"limit": 0}).status_code == 422


# ───────────── SPA: nunca fuera de dist, nunca eclipsa /api ─────────────


def _fake_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>ts</title>")
    (dist / "favicon.svg").write_text("<svg/>")
    (tmp_path / "perfil.yaml").write_text("usuario: privado")
    return dist


def test_spa_mount_serves_index_but_never_api_nor_outside_dist(tmp_path: Path):
    from atlas_core.api.app import mount_frontend

    dist = _fake_dist(tmp_path)
    (dist / "leak").symlink_to(tmp_path / "perfil.yaml")
    a = FastAPI()
    mount_frontend(a, dist)
    with TestClient(a) as c:
        r = c.get("/")
        assert r.status_code == 200 and "text/html" in r.headers["content-type"]
        assert c.get("/brief").text.startswith("<!doctype html>")
        assert c.get("/favicon.svg").status_code == 200 and c.get("/favicon.svg").text == "<svg/>"
        for path in ("/api/does-not-exist", "/api/machine/nope", "/api", "/api/"):
            r = c.get(path)
            assert r.status_code == 404 and "application/json" in r.headers["content-type"], path
        # traversal (%2e%2e llega al ASGI como '..'; httpx normaliza el '..' literal) y enlace simbólico
        for path in (
            "/%2e%2e/perfil.yaml",
            "/assets/%2e%2e/%2e%2e/perfil.yaml",
            "/x/%2e%2e/%2e%2e/perfil.yaml",
        ):
            r = c.get(path)
            assert r.status_code == 404 and "privado" not in r.text, path
        r = c.get("/leak")
        assert "privado" not in r.text and "text/html" in r.headers["content-type"]


def test_no_frontend_branch(tmp_path: Path):
    from atlas_core.api.app import mount_frontend

    a = FastAPI()
    mount_frontend(a, tmp_path / "missing")
    with TestClient(a) as c:
        r = c.get("/")
        assert r.status_code == 200 and "Frontend no compilado" in r.json()["message"]
        assert c.get("/api/does-not-exist").status_code == 404


def test_unknown_api_route_is_json_404(client):
    # válido con dist compilado (guard del catch-all) y sin él (404 nativo)
    for path in ("/api/no-existe", "/api/events/x/y/z", "/api", "/api/"):
        r = client.get(path)
        assert r.status_code == 404, (path, r.status_code)
        assert "application/json" in r.headers.get("content-type", ""), path
    assert client.get("/api/health").status_code == 200


# ───────────── CSRF y Host ─────────────


def _insert_alert(seeded) -> None:
    from atlas_core.db import dumps, now_iso

    seeded.insert(
        "alert",
        {
            "id": "a1",
            "kind": "test",
            "title": "t",
            "body": None,
            "ref": dumps({}),
            "created_at": now_iso(),
            "read": 0,
        },
    )


def test_cross_site_requests_with_effects_are_rejected(client, seeded):
    _insert_alert(seeded)
    form = {"Content-Type": "application/x-www-form-urlencoded"}
    # navegador moderno: <form method=post> desde otra web
    r = client.post(
        "/api/alerts/read",
        headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site", **form},
        content="x=1",
    )
    assert r.status_code == 403 and "cross-site" in r.json()["detail"]
    # navegador antiguo: sin Sec-Fetch-*, pero con Origin
    r = client.post("/api/alerts/read", headers={"Origin": "https://evil.example", **form}, content="x=1")
    assert r.status_code == 403
    assert seeded.scalar("SELECT read FROM alert WHERE id = 'a1'") == 0
    # <img src=".../api/agents/deepen/x">: GET con coste, rechazado antes de _require() (sin clave sería 409)
    r = client.get(
        "/api/agents/deepen/x",
        headers={"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "no-cors", "Sec-Fetch-Dest": "image"},
    )
    assert r.status_code == 403
    # DNS rebinding: Host ajeno → 400 incluso en lecturas
    assert client.get("/api/mando", headers={"Host": "evil.attacker.net"}).status_code == 400
    assert client.get("/api/health", headers={"Host": "localhost:5173"}).status_code == 200
    # lecturas seguras cross-site no se bloquean aquí (sin CORS el navegador no puede leerlas)
    assert client.get("/api/health", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 200


def test_same_origin_and_non_browser_clients_still_allowed(client, seeded):
    _insert_alert(seeded)
    # la SPA (o el proxy de Vite): same-origin
    r = client.post(
        "/api/alerts/read", headers={"Sec-Fetch-Site": "same-origin", "Origin": "http://127.0.0.1:8765"}
    )
    assert r.status_code == 200 and seeded.scalar("SELECT read FROM alert WHERE id = 'a1'") == 1
    # navegador antiguo desde el propio frontend de desarrollo
    assert client.post("/api/alerts/read", headers={"Origin": "http://localhost:5173"}).status_code == 200
    # navegación directa (barra de direcciones, /api/docs)
    assert client.post("/api/alerts/read", headers={"Sec-Fetch-Site": "none"}).status_code == 200
    # curl / scripts / esta suite: sin cabeceras de navegador
    assert client.post("/api/alerts/read").status_code == 200
