"""Pipeline de ingesta: aislamiento de fuentes rotas, plazo total por fuente, cerrojo entre pasadas (hilos y
procesos), deduplicación de afirmaciones tras fusionar eventos, tope de published_at, índice de canonical_url y
reparación de URLs relativas."""

from __future__ import annotations

import asyncio
import re
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from atlas_core import pipeline as pl
from atlas_core.connectors.base import FetchResult, RawItem
from atlas_core.connectors.rss import RSSConnector
from atlas_core.db import dumps, loads, now_iso
from atlas_core.util import parse_iso
from conftest import make_doc, make_source

TITLE = "El Gobierno aprueba la ley de presupuestos con 176 votos a favor y entra en vigor mañana"
LEDE = "La norma fue aprobada por el Congreso según el Ministerio de Hacienda tras un largo debate."


def _item(url: str, title: str = TITLE, published_at: str | None = None) -> RawItem:
    return RawItem(url=url, title=title, summary=LEDE, published_at=published_at)


# ───────── aislamiento de fuentes y plazo total ─────────


async def test_run_ingest_isolates_a_broken_source(db, monkeypatch):
    """Una URL de feed inválida (httpx.InvalidURL no es HTTPError) ya no aborta la pasada ni queda sin rastro."""
    make_source(db, "sana")
    make_source(db, "rota", feeds=["https://[::1/rss"])

    async def fake_fetch(self, source, client):
        if source["slug"] == "rota":
            raise httpx.InvalidURL("Invalid port: ':1'")
        return FetchResult(items=[_item("https://sana.example/1")])

    monkeypatch.setattr(RSSConnector, "fetch", fake_fetch)
    stats = await pl.run_ingest(db, force=True)  # no lanza
    assert stats["fetch"]["failed"] == 1 and stats["fetch"]["ok"] == 1 and stats["fetch"]["new_docs"] == 1
    assert any(e.startswith("rota: InvalidURL") for e in stats["fetch"]["errors"])
    health = {
        r["slug"]: dict(r)
        for r in db.all(
            "SELECT s.slug, h.ok, h.error FROM source_health h JOIN source s ON s.id = h.source_id"
        )
    }
    assert health["sana"]["ok"] == 1 and health["sana"]["error"] is None
    assert health["rota"]["ok"] == 0 and health["rota"]["error"].startswith("InvalidURL")
    assert db.scalar("SELECT COUNT(*) FROM source WHERE last_polled_at IS NULL") == 0
    assert db.one("SELECT last_error FROM source WHERE slug = 'rota'")["last_error"].startswith("InvalidURL")
    # process_new_documents sí corrió: el documento de la fuente sana tiene evento
    assert db.scalar("SELECT COUNT(*) FROM document WHERE event_id IS NOT NULL") == 1
    assert db.one("SELECT ok, error FROM job_run WHERE job = 'ingest'")["ok"] == 1
    # con last_polled_at fijado, la fuente rota deja de ser «due» hasta el próximo intervalo
    assert pl.due_sources(db) == []


async def test_source_total_timeout_is_recorded_as_failure(db, monkeypatch):
    """Plazo total por fuente: un servidor que gotea no retiene la pasada (el timeout de httpx es por fragmento)."""
    make_source(db, "goteo")
    monkeypatch.setattr(pl.settings, "atlas_source_timeout", 0.05)

    async def drip(self, source, client):
        await asyncio.sleep(2)
        return FetchResult(items=[_item("https://goteo.example/1")])

    monkeypatch.setattr(RSSConnector, "fetch", drip)
    stats = await pl.fetch_sources(db, pl.due_sources(db, force=True))
    assert stats["failed"] == 1 and stats["ok"] == 0 and stats["errors"][0].startswith("goteo: TimeoutError")
    h = db.one("SELECT ok, error, latency_ms FROM source_health")
    assert h["ok"] == 0 and h["error"].startswith("TimeoutError") and h["latency_ms"] is not None
    assert db.one("SELECT last_polled_at FROM source")["last_polled_at"] is not None


# ───────── cerrojo entre pasadas ─────────


async def test_two_concurrent_ingests_only_one_runs(db, monkeypatch):
    make_source(db, "lenta")

    async def slow_fetch(self, source, client):
        await asyncio.sleep(0.2)
        return FetchResult(items=[_item("https://lenta.example/1")])

    monkeypatch.setattr(RSSConnector, "fetch", slow_fetch)
    r1, r2 = await asyncio.gather(pl.run_ingest(db, force=True), pl.run_ingest(db, force=True))
    ran, skipped = (r1, r2) if "fetch" in r1 else (r2, r1)
    assert skipped == {"started": False, "reason": pl.BUSY_REASON}
    assert ran["fetch"]["new_docs"] == 1 and ran["process"]["docs"] == 1
    jobs = db.all("SELECT ok, error FROM job_run WHERE job = 'ingest'")
    assert sorted((j["ok"], j["error"]) for j in jobs) == [(0, pl.BUSY_REASON), (1, None)]
    assert db.scalar("SELECT COUNT(*) FROM event") == 1 and db.scalar("SELECT COUNT(*) FROM claim") >= 1
    dup_claims = db.scalar(
        "SELECT COUNT(*) FROM (SELECT 1 FROM claim GROUP BY document_id, text_canonical HAVING COUNT(*) > 1)"
    )
    assert dup_claims == 0


def test_recompute_is_blocked_while_ingest_holds_the_lock(db):
    with pl.job_lock(db):
        assert pl.recompute_events(db) == {
            "events": 0,
            "consolidated": 0,
            "started": False,
            "reason": pl.BUSY_REASON,
        }
    assert "started" not in pl.recompute_events(db)  # cerrojo liberado


def test_job_lock_excludes_other_threads(db):
    got: list[bool] = []

    def worker() -> None:
        try:
            with pl.job_lock(db):
                got.append(True)
        except pl.JobBusy:
            got.append(False)

    with pl.job_lock(db):
        t = threading.Thread(target=worker)
        t.start()
        t.join()
    assert got == [False]
    worker()
    assert got == [False, True]


# ───────── afirmaciones duplicadas tras fusionar eventos ─────────


def test_dedup_event_claims_moves_evidence_and_records_revisions(db):
    s1 = make_source(db, "d1")
    s2 = make_source(db, "d2", country="FR", bloc="eu")
    d1 = make_doc(db, s1, TITLE)
    d2 = make_doc(db, s2, TITLE)
    ts = now_iso()
    db.exec(
        "INSERT INTO event(id, title_neutral, first_seen_at, last_update_at) VALUES ('e1', ?, ?, ?)",
        (TITLE, ts, ts),
    )
    # dos pasadas concurrentes dejaron la misma afirmación del mismo documento dos veces en el evento
    for cid, created in (("c_old", "2026-01-01T00:00:00+00:00"), ("c_new", "2026-01-02T00:00:00+00:00")):
        db.exec(
            "INSERT INTO claim(id, event_id, document_id, text_canonical, level, status, extracted_by, created_at) "
            "VALUES (?, 'e1', ?, ?, 'fact', 'unverified', 'heuristic:v1', ?)",
            (cid, d1, TITLE, created),
        )
    for eid, cid, doc, quote in (
        ("ev1", "c_old", d1, TITLE),
        ("ev2", "c_new", d1, TITLE),  # copia idéntica: no se mueve
        ("ev3", "c_new", d2, "Otra cita distinta del segundo medio"),  # evidencia nueva: pasa a la conservada
    ):
        db.exec(
            "INSERT INTO claim_evidence(id, claim_id, document_id, stance, quote, created_at) VALUES (?,?,?,'supports',?,?)",
            (eid, cid, doc, quote, ts),
        )
    assert pl.dedup_event_claims(db, "e1") == 1
    dup = db.one("SELECT status, event_id FROM claim WHERE id = 'c_new'")
    assert dup["status"] == "merged" and dup["event_id"] is None
    assert {r["id"] for r in db.all("SELECT id FROM claim_evidence WHERE claim_id = 'c_old'")} == {
        "ev1",
        "ev3",
    }
    assert db.one("SELECT claim_id FROM claim_evidence WHERE id = 'ev2'")["claim_id"] == "c_new"
    assert db.one("SELECT status FROM claim WHERE id = 'c_old'")["status"] == "confirmed"  # 2 fuentes tier 2
    revs = db.all(
        "SELECT claim_id, old_status, new_status, evidence_ids FROM claim_revision ORDER BY claim_id"
    )
    assert [(r["claim_id"], r["old_status"], r["new_status"]) for r in revs] == [
        ("c_new", "unverified", "merged"),
        ("c_old", "unverified", "confirmed"),
    ]
    assert loads(revs[0]["evidence_ids"]) == ["ev3"]
    assert pl.dedup_event_claims(db, "e1") == 0  # idempotente


# ───────── published_at acotado ─────────


def test_insert_documents_caps_future_published_at(db):
    sid = make_source(db, "rbi", type="central_bank", languages=["en"])
    src = {"id": sid, "type": "central_bank", "languages": ["en"]}
    future = (datetime.now(UTC) + timedelta(hours=5)).replace(microsecond=0).isoformat()  # hora IST sin zona
    near = (datetime.now(UTC) + timedelta(minutes=5)).replace(microsecond=0).isoformat()  # desfase de reloj
    conn = RSSConnector()
    docs = [
        conn.normalize(src, _item("https://rbi.example/1", published_at=future)),
        conn.normalize(src, _item("https://rbi.example/2", title=TITLE + " (bis)", published_at=near)),
    ]
    assert pl.insert_documents(db, src, docs) == (2, 0)
    r1 = db.one("SELECT published_at, fetched_at, meta FROM document WHERE url = 'https://rbi.example/1'")
    assert parse_iso(r1["published_at"]) <= parse_iso(r1["fetched_at"]) + pl.PUBLISHED_AT_SKEW
    assert loads(r1["meta"])["published_at_reported"] == future  # el original no se pierde
    r2 = db.one("SELECT published_at, meta FROM document WHERE url = 'https://rbi.example/2'")
    assert r2["published_at"] == near and "published_at_reported" not in loads(r2["meta"])


# ───────── índice y formato de fechas ─────────


def test_document_dedup_lookup_uses_indexes_not_a_scan(db):
    assert "ix_document_canonical" in {r[1] for r in db.all("PRAGMA index_list(document)")}
    plan = " ".join(
        r["detail"]
        for r in db.all(
            "EXPLAIN QUERY PLAN SELECT 1 FROM document WHERE url = ? OR canonical_url = ? OR (content_hash = ? AND source_id = ?)",
            ("a", "b", "c", "d"),
        )
    )
    assert "SCAN document" not in plan and "ix_document_canonical" in plan


def test_ingest_modules_never_compare_dates_with_sqlite_now():
    """La función datetime de SQLite devuelve 'YYYY-MM-DD HH:MM:SS' (espacio) y las columnas llevan 'T':
    la comparación de cadenas alarga las ventanas hasta 24 h. Usar since_iso()."""
    root = Path(pl.__file__).parent
    files = [root / "pipeline.py", root / "scheduler.py", root / "db.py", *(root / "connectors").glob("*.py")]
    offenders = [
        p.name for p in files if re.search(r"""datetime\(['"]now['"]""", p.read_text(encoding="utf-8"))
    ]
    assert offenders == []


# ───────── reparación única de URLs relativas ─────────


def test_repair_relative_urls_resolves_and_merges_duplicates(db):
    trt = make_source(db, "trtworld", feeds=["https://www.trtworld.com/feed/rss.xml"])
    bea = make_source(db, "bea", feeds=["https://apps.bea.gov/rss/rss.xml"])
    db.exec("UPDATE source SET domain = 'bea.gov' WHERE id = ?", (bea,))
    feed_meta = dumps({"feed": "https://www.trtworld.com/feed/rss.xml"})
    old1 = make_doc(db, trt, TITLE, url="/article/1")
    old2 = make_doc(db, trt, TITLE + " (dos)", url="/article/2")
    new2 = make_doc(db, trt, TITLE + " (dos)", url="https://www.trtworld.com/article/2")  # ya reingestado
    oldb = make_doc(db, bea, "GDP advance estimate for the fourth quarter", url="www.bea.gov/news/2026/gdp")
    db.exec("UPDATE document SET meta = ? WHERE id IN (?, ?)", (feed_meta, old1, old2))
    db.exec(
        "UPDATE document SET meta = ? WHERE id = ?",
        (dumps({"feed": "https://apps.bea.gov/rss/rss.xml"}), oldb),
    )
    # relaciones del duplicado que deben sobrevivir a la fusión
    ts = now_iso()
    db.exec(
        "INSERT INTO event(id, title_neutral, first_seen_at, last_update_at, n_docs, lead_document_id) VALUES ('e1', ?, ?, ?, 1, ?)",
        (TITLE, ts, ts, old2),
    )
    db.exec("UPDATE document SET event_id = 'e1' WHERE id = ?", (old2,))
    db.exec("INSERT INTO event_document(event_id, document_id, similarity) VALUES ('e1', ?, 1.0)", (old2,))
    db.exec("INSERT INTO entity(id, kind, name, created_at) VALUES ('ent1', 'country', 'España', ?)", (ts,))
    db.exec("INSERT INTO document_entity(document_id, entity_id, salience) VALUES (?, 'ent1', 0.5)", (old2,))
    db.exec(
        "INSERT INTO claim(id, event_id, document_id, text_canonical, level, status, extracted_by, created_at) "
        "VALUES ('c1', 'e1', ?, ?, 'fact', 'unverified', 'heuristic:v1', ?)",
        (old2, TITLE, ts),
    )
    db.exec("INSERT INTO reading_log(document_id, action, at) VALUES (?, 'open', ?)", (old2, ts))

    dry = pl.repair_relative_urls(db)
    assert dry == {"candidates": 3, "fixed": 2, "merged": 1, "unresolved": 0, "applied": False}
    assert (
        db.scalar("SELECT COUNT(*) FROM document WHERE url NOT LIKE 'http%'") == 3
    )  # sin --apply no toca nada

    res = pl.repair_relative_urls(db, apply=True)
    assert res["fixed"] == 2 and res["merged"] == 1 and res["applied"]
    assert sorted(r["url"] for r in db.all("SELECT url FROM document")) == [
        "https://www.bea.gov/news/2026/gdp",
        "https://www.trtworld.com/article/1",
        "https://www.trtworld.com/article/2",
    ]
    fixed = db.one("SELECT id, canonical_url FROM document WHERE url = 'https://www.trtworld.com/article/1'")
    assert fixed["id"] == old1 and fixed["canonical_url"] == "https://www.trtworld.com/article/1"
    keep = db.one("SELECT id, event_id FROM document WHERE url = 'https://www.trtworld.com/article/2'")
    assert keep["id"] == new2 and keep["event_id"] == "e1"
    for sql in (
        "SELECT document_id FROM claim WHERE id = 'c1'",
        "SELECT document_id FROM document_entity WHERE entity_id = 'ent1'",
        "SELECT document_id FROM event_document WHERE event_id = 'e1'",
        "SELECT document_id FROM reading_log",
        "SELECT lead_document_id AS document_id FROM event WHERE id = 'e1'",
    ):
        assert db.one(sql)["document_id"] == new2, sql
    assert db.scalar("SELECT COUNT(*) FROM document_fts WHERE doc_id = ?", (old2,)) == 0
    assert db.scalar("SELECT COUNT(*) FROM document_fts") == 3
    assert db.one("SELECT n_docs FROM event WHERE id = 'e1'")["n_docs"] == 1
    assert pl.repair_relative_urls(db)["candidates"] == 0
