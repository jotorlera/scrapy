"""API: salud, semilla, radar, ciclo completo de pronóstico, notas y mapas argumentales, agentes sin clave."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from conftest import make_doc, make_source


@pytest.fixture()
def client(seeded):
    from atlas_core.api.app import app

    with TestClient(app) as c:
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
        make_doc(seeded, s, title, "La norma limita los alquileres en zonas tensionadas según el Ministerio de Vivienda.")
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


def test_forecast_full_cycle_user_before_system(client):
    r = client.post("/api/forecasts", json={"title": "corto", "resolution_criteria": "x", "close_at": "2027-01-01T00:00:00+00:00"})
    assert r.status_code == 422
    r = client.post(
        "/api/forecasts",
        json={
            "title": "¿Aprobará el Congreso los presupuestos antes del 31 de diciembre de 2026?",
            "resolution_criteria": "SÍ si el BOE publica la Ley de Presupuestos Generales del Estado antes del 31-12-2026 (fuente: boe.es).",
            "resolution_source": "BOE",
            "close_at": "2026-12-31T00:00:00+00:00",
            "base_rate": 0.45,
            "base_rate_note": "frecuencia histórica de aprobación en plazo",
        },
    )
    assert r.status_code == 200, r.text
    qid = r.json()["id"]
    q = client.get(f"/api/forecasts/{qid}").json()
    assert q["latest"]["base_rate"]["p"] == 0.45
    r = client.post(f"/api/forecasts/{qid}/forecast", json={"probability": 0.7, "rationale": "mayoría estable"})
    assert r.json()["system_probability"] == 0.45
    r = client.post(f"/api/forecasts/{qid}/resolve", json={"outcome": 1})
    scores = r.json()["scores"]
    assert scores["user"]["brier"] == pytest.approx(0.09) and scores["base_rate"]["brier"] == pytest.approx(0.3025)
    cal = client.get("/api/forecasts/calibration", params={"forecaster": "user"}).json()
    assert cal["calibration"]["n"] == 1
    assert any(s["forecaster"] == "user" and s["bss_vs_base_rate"] > 0 for s in cal["summary"])


def test_notes_backlinks_and_cards(client):
    a = client.post("/api/notes", json={"title": "Libertad negativa", "body_text": "Berlin distingue dos conceptos. Ver [[Pettit]]."}).json()["id"]
    b = client.post("/api/notes", json={"title": "Pettit", "body_text": "Libertad como no dominación. Relación con [[Libertad negativa]]."}).json()["id"]
    n = client.get(f"/api/notes/{a}").json()
    assert n["links"] == ["Pettit"] and any(x["id"] == b for x in n["backlinks"])
    assert client.get(f"/api/notes/{a}/export.md").text.startswith("# Libertad negativa")
    cid = client.post("/api/cards", json={"front": "¿Quién formuló la libertad como no dominación?", "back": "Philip Pettit"}).json()["id"]
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
    nid = client.post(f"/api/agora/maps/{rbu['id']}/nodes", json={"kind": "premise", "text": "Premisa sin apoyo añadida por el usuario"}).json()["id"]
    m2 = client.get(f"/api/agora/maps/{rbu['id']}").json()
    assert any(u["id"] == nid for u in m2["analysis"]["unsupported"])
    assert client.get("/api/agora/genealogy").json()["nodes"]


def test_agents_disabled_without_key(client, monkeypatch):
    from atlas_core import llm as llm_mod

    monkeypatch.setattr(llm_mod.settings, "anthropic_api_key", None)
    llm_mod._llm = None
    st = client.get("/api/agents/status").json()
    assert st["enabled"] is False and "ANTHROPIC_API_KEY" in st["message"]
    assert client.get("/api/agents/deepen/whatever").status_code == 409
    assert client.post("/api/agents/red_team/whatever").status_code == 409


def test_machine_room_and_settings(client):
    m = client.get("/api/machine").json()
    assert m["totals"]["sources_total"] > 150 and "budget" in m and m["budget"]["daily_cap_usd"] == 10
    s = client.put("/api/settings", json={"theme": "dark", "cat_enabled": False}).json()
    assert s["theme"] == "dark" and s["cat_enabled"] is False
    assert client.get("/api/settings").json()["theme"] == "dark"
    b = client.post("/api/brief/generate").json()["brief"]
    assert b["composed_by"] == "rules" and "socratic_prompt" in b


def test_mando_and_diet(client):
    m = client.get("/api/mando").json()
    assert len(m["businesses"]) == 4
    did = client.post("/api/mando/decisions", json={"title": "Abrir sede en Andorra", "premises": ["fiscalidad estable"], "success_probability": 0.6, "premortem": "fracasó por falta de talento local"}).json()["id"]
    assert client.post(f"/api/mando/decisions/{did}/outcome", json={"outcome": "en curso"}).json()["ok"]
    assert client.post("/api/diet/log", json={"action": "open", "seconds": 120, "topic": "Migración"}).json()["ok"]
    rep = client.get("/api/diet/report").json()
    assert rep["n_logs"] == 1 and "entropy" in rep
