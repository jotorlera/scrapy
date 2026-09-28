"""Ventanas temporales con filas fuera de la ventana (radar, MANDO alerts_7d, Sala de Máquinas documents_24h).

Regresión del formato: now_iso() escribe 'YYYY-MM-DDTHH:MM:SS+00:00' y `datetime('now', '-N hours')` de SQLite
devuelve 'YYYY-MM-DD HH:MM:SS' (espacio). Como 'T' > ' ', cualquier fila del mismo día UTC que el límite pasaba
el filtro aunque fuera anterior. Estas pruebas siembran timestamps distintos de «ahora» (conftest.iso_ago) para
que el filtro se compruebe de verdad; el umbral debe calcularse en Python (db.since_iso) con el mismo formato.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from atlas_core.db import dumps, new_id
from conftest import iso_ago, make_doc, make_source

TITLE = "El Gobierno de España aprueba la ley de vivienda y entra en vigor en enero"
LEDE = "La norma limita los alquileres en zonas tensionadas según el Ministerio de Vivienda."


@pytest.fixture()
def client(seeded):
    from atlas_core.api.app import app

    with TestClient(app, base_url="http://127.0.0.1:8765") as c:
        yield c


def _event(db, eid: str, at: str, materiality: float = 50) -> None:
    db.exec(
        "INSERT INTO event(id,title_neutral,countries,first_seen_at,last_update_at,n_docs,materiality) "
        "VALUES (?,?,?,?,?,1,?)",
        (eid, f"Evento {eid}", dumps(["ES"]), at, at, materiality),
    )


def test_radar_window_excludes_events_older_than_window(client, seeded):
    from atlas_core.pipeline import process_new_documents

    old = iso_ago(hours=3)
    s1, s2 = make_source(seeded, "w1"), make_source(seeded, "w2", ideology="right")
    for s in (s1, s2):
        make_doc(seeded, s, TITLE, LEDE, published_at=old)
    process_new_documents(seeded, use_llm=False)
    assert seeded.scalar("SELECT COUNT(*) FROM event WHERE status != 'merged'") == 1
    assert client.get("/api/radar", params={"hours": 1}).json()["events"] == []
    assert len(client.get("/api/radar", params={"hours": 6}).json()["events"]) == 1


def test_radar_stats_count_only_the_window(client, seeded):
    """Los contadores del radar (eventos/documentos) usan la misma ventana que la lista."""
    from atlas_core.pipeline import process_new_documents

    s1, s2 = make_source(seeded, "w3"), make_source(seeded, "w4", ideology="right")
    for s in (s1, s2):
        make_doc(seeded, s, TITLE, LEDE, published_at=iso_ago(hours=3))
    process_new_documents(seeded, use_llm=False)
    body = client.get("/api/radar", params={"hours": 1}).json()
    assert body["counts"]["events"] == 0, "counts.events cuenta un evento de hace 3 h en una ventana de 1 h"
    assert body["counts"]["documents"] == 0, (
        "counts.documents cuenta documentos de hace 3 h en una ventana de 1 h"
    )
    assert body["by_domain"] == {}
    body6 = client.get("/api/radar", params={"hours": 6}).json()
    assert body6["counts"]["events"] == 1 and body6["counts"]["documents"] == 2


def test_mando_alerts_7d_excludes_alerts_older_than_seven_days(client, seeded):
    biz = seeded.all("SELECT id FROM business_unit")
    assert len(biz) == 4  # perfil de pruebas (tests/fixtures/perfil.test.yaml)
    bid = biz[0]["id"]
    # Una alerta de hace 7 d + 3 h (mismo día UTC que el límite, pero anterior) y otra de hace 7 d − 3 h.
    for eid, at in (("old_ev", iso_ago(hours=7 * 24 + 3)), ("new_ev", iso_ago(hours=7 * 24 - 3))):
        _event(seeded, eid, at)
        seeded.exec(
            "INSERT INTO exposure_alert(id, business_id, event_id, channel, explanation, confidence, created_at, dismissed) "
            "VALUES (?,?,?,?,?,?,?,0)",
            (new_id(), bid, eid, "regulatory", "prueba", 0.5, at),
        )
    m = client.get("/api/mando").json()
    by_id = {b["id"]: b for b in m["businesses"]}
    assert by_id[bid]["alerts_7d"] == 1


def test_machine_documents_24h_excludes_documents_older_than_a_day(client, seeded):
    s = make_source(seeded, "w5")
    make_doc(seeded, s, "Documento antiguo", "de hace 27 horas", published_at=iso_ago(hours=27))
    make_doc(seeded, s, "Documento reciente", "de hace 3 horas", published_at=iso_ago(hours=3))
    m = client.get("/api/machine").json()
    assert m["totals"]["documents"] == 2
    assert m["totals"]["documents_24h"] == 1
    src = next(x for x in m["sources"] if x["id"] == s)
    assert src["docs_24h"] == 1


def test_alerts_high_materiality_uses_a_24h_window_not_the_calendar_day(client, seeded):
    _event(seeded, "hi_old", iso_ago(hours=27), materiality=90)
    _event(seeded, "hi_new", iso_ago(hours=3), materiality=90)
    high = client.get("/api/alerts").json()["high_materiality"]
    assert [e["id"] for e in high] == ["hi_new"]
