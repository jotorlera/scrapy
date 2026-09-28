"""Pipeline de ingesta (docs/spec/01 §4):

fuente → conector.fetch() → documento → deduplicación → embedding → entidades (gazetteer) → evento (clustering)
→ afirmaciones con cita → cobertura y silencio → materialidad → deltas de estado → exposición (MANDO).
Con clave de API y presupuesto: extractor Haiku para las fuentes de tier ≤ 3 y títulos neutros para eventos con
≥ 3 documentos.
"""

from __future__ import annotations

import asyncio
import time
from datetime import timedelta
from typing import Any

from .connectors.base import make_client
from .connectors.markets import refresh_markets
from .connectors.prediction_markets import refresh_prediction_markets
from .connectors.rss import RSSConnector
from .db import Database, dumps, loads, new_id, now_iso, row_to_dict, vec_to_blob
from .embed import IDF, get_embedder, set_idf
from .engines.claims import heuristic_claims, persist_claims
from .engines.cluster import ClusterIndex, consolidate_events
from .engines.coverage import baseline_shares, compute_coverage
from .engines.exposure import evaluate_event
from .engines.materiality import compute_materiality
from .engines.state import deltas_from_event, deltas_from_markets
from .gazetteer import (
    classify_domain,
    countries_from_mentions,
    find_mentions,
    principal_keys,
    topics_from_mentions,
)
from .settings import settings
from .util import parse_iso

MAX_ITEMS_PER_SOURCE_PER_RUN = 60
MAX_ITEMS_BULLETIN = 40  # boletines oficiales y agencias muy prolíficas


def _job_start(db: Database, job: str) -> int:
    with db.tx() as conn:
        cur = conn.execute("INSERT INTO job_run(job, started_at) VALUES (?, ?)", (job, now_iso()))
        return int(cur.lastrowid)


def _job_end(db: Database, job_id: int, ok: bool, stats: dict[str, Any], error: str | None = None) -> None:
    with db.tx() as conn:
        conn.execute(
            "UPDATE job_run SET finished_at = ?, ok = ?, stats = ?, error = ? WHERE id = ?",
            (now_iso(), 1 if ok else 0, dumps(stats), error, job_id),
        )


def due_sources(db: Database, force: bool = False, limit: int | None = None) -> list[dict[str, Any]]:
    rows = db.all(
        "SELECT * FROM source WHERE active = 1 AND feeds != '[]' ORDER BY tier ASC, last_polled_at ASC"
    )
    out = []
    now = parse_iso(now_iso())
    for r in rows:
        d = row_to_dict(r, ("feeds", "languages"))
        if not force and d.get("last_polled_at"):
            last = parse_iso(d["last_polled_at"])
            if last and now and (now - last) < timedelta(minutes=int(d.get("poll_minutes") or 30)):
                continue
        out.append(d)
        if limit and len(out) >= limit:
            break
    return out


async def fetch_sources(db: Database, sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Descarga feeds en paralelo, registra salud e inserta documentos nuevos."""
    conn_rss = RSSConnector()
    sem = asyncio.Semaphore(settings.atlas_ingest_concurrency)
    stats = {
        "sources": len(sources),
        "ok": 0,
        "failed": 0,
        "not_modified": 0,
        "new_docs": 0,
        "dup_docs": 0,
        "errors": [],
    }

    async def one(src: dict[str, Any], client) -> None:
        async with sem:
            res = await conn_rss.fetch(src, client)
        ts = now_iso()
        with db.tx() as c:
            c.execute(
                "INSERT INTO source_health(source_id, checked_at, ok, items, error, latency_ms) VALUES (?,?,?,?,?,?)",
                (src["id"], ts, 1 if res.ok else 0, len(res.items), res.error, res.latency_ms),
            )
            fields = {"last_polled_at": ts, "last_error": res.error}
            if res.ok:
                fields.update({"last_ok_at": ts, "last_items": len(res.items)})
                if res.etag:
                    fields["etag"] = res.etag
                if res.last_modified:
                    fields["last_modified"] = res.last_modified
            sets = ", ".join(f"{k} = ?" for k in fields)
            c.execute(f"UPDATE source SET {sets} WHERE id = ?", (*fields.values(), src["id"]))
        if res.not_modified:
            stats["not_modified"] += 1
        if not res.ok:
            stats["failed"] += 1
            if res.error:
                stats["errors"].append(f"{src['slug']}: {res.error[:120]}")
            return
        stats["ok"] += 1
        cap = (
            MAX_ITEMS_BULLETIN
            if src.get("type") in ("institution", "statistical_office", "court")
            else MAX_ITEMS_PER_SOURCE_PER_RUN
        )
        new, dup = insert_documents(db, src, [conn_rss.normalize(src, it) for it in res.items[:cap]])
        stats["new_docs"] += new
        stats["dup_docs"] += dup

    async with make_client() as client:
        await asyncio.gather(*(one(s, client) for s in sources))
    return stats


def insert_documents(db: Database, source: dict[str, Any], docs: list) -> tuple[int, int]:
    new = dup = 0
    ts = now_iso()
    with db.tx() as conn:
        for d in docs:
            if d is None:
                continue
            exists = conn.execute(
                "SELECT 1 FROM document WHERE url = ? OR canonical_url = ? OR (content_hash = ? AND source_id = ?)",
                (d.url, d.canonical_url, d.content_hash, d.source_id),
            ).fetchone()
            if exists:
                dup += 1
                continue
            doc_id = new_id()
            conn.execute(
                """INSERT INTO document(id, source_id, kind, url, canonical_url, title, lede, text, lang, authors, published_at,
                   fetched_at, content_hash, extraction_method, paywalled, meta)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    doc_id,
                    d.source_id,
                    d.kind,
                    d.url,
                    d.canonical_url,
                    d.title,
                    d.lede,
                    d.text,
                    d.lang,
                    dumps(d.authors),
                    d.published_at or ts,
                    ts,
                    d.content_hash,
                    d.extraction_method,
                    1 if d.paywalled else 0,
                    dumps(d.meta),
                ),
            )
            conn.execute(
                "INSERT INTO document_fts(doc_id, title, lede, text) VALUES (?,?,?,?)",
                (doc_id, d.title, d.lede, d.text[:5000]),
            )
            new += 1
    return new, dup


def _entity_cache(db: Database) -> dict[str, str]:
    rows = db.all(
        "SELECT id, json_extract(attributes, '$.key') AS k FROM entity WHERE json_extract(attributes, '$.key') IS NOT NULL"
    )
    return {r["k"]: r["id"] for r in rows if r["k"]}


def process_new_documents(
    db: Database, max_docs: int = 1500, use_llm: bool | None = None, max_batches: int = 6
) -> dict[str, Any]:
    """Procesa por lotes todos los documentos sin evento y consolida eventos duplicados al final."""
    total: dict[str, Any] = {}
    for _ in range(max_batches):
        st = _process_batch(db, max_docs=max_docs, use_llm=use_llm)
        for k, v in st.items():
            if isinstance(v, (int, float)):
                total[k] = total.get(k, 0) + v
        if st["docs"] < max_docs:
            break
    cons = consolidate_events(db)
    total["consolidated"] = cons.get("merged", 0)
    for eid in cons.get("winners", []) or []:
        compute_coverage(db, eid)
        compute_materiality(db, eid)
        deltas_from_event(db, eid)
        evaluate_event(db, eid)
    return total


def _process_batch(db: Database, max_docs: int, use_llm: bool | None) -> dict[str, Any]:
    """Embeddings, entidades, clustering y afirmaciones para un lote de documentos sin evento."""
    emb = get_embedder()
    # IDF sobre el corpus reciente: las palabras raras (nombres propios) pesan; el boilerplate, no
    corpus = [
        f"{r['title']} {r['lede'] or ''}"
        for r in db.all("SELECT title, lede FROM document ORDER BY fetched_at DESC LIMIT 20000")
    ]
    set_idf(IDF.from_texts(corpus))
    idx = ClusterIndex(db)
    ent_cache = _entity_cache(db)
    rows = db.all(
        """SELECT d.*, s.tier, s.type AS stype, s.name AS sname, s.country AS scountry FROM document d JOIN source s ON s.id = d.source_id
           WHERE d.event_id IS NULL ORDER BY d.published_at DESC LIMIT ?""",
        (max_docs,),
    )
    stats = {
        "docs": len(rows),
        "new_events": 0,
        "joined": 0,
        "claims_new": 0,
        "claims_merged": 0,
        "claims_dropped": 0,
        "llm_docs": 0,
    }
    touched: set[str] = set()
    llm = None
    if use_llm is None:
        use_llm = settings.llm_enabled
    if use_llm:
        from .llm import BudgetExceeded, LLMUnavailable, get_llm

        llm = get_llm(db)
    for r in rows:
        doc = dict(r)
        source = {"id": doc["source_id"], "name": doc["sname"], "tier": doc["tier"], "type": doc["stype"]}
        text_for_embedding = (
            f"{doc['title']}. {doc['title']}. {doc['lede'] or ''} {(doc['text'] or '')[:800]}"
        )
        mentions = find_mentions(f"{doc['lede'] or ''}\n{(doc['text'] or '')[:3000]}", doc["title"])
        countries = countries_from_mentions(mentions)
        keys = principal_keys(mentions)
        topics = topics_from_mentions(mentions)
        scountry = doc.get("scountry")
        national_source = bool(scountry) and scountry not in ("EU", "UN")
        # sin país explícito, un medio nacional habla de su país (tier 2-3, prensa)
        if (
            not countries
            and national_source
            and doc["stype"] in ("newspaper", "broadcaster", "digital_native", "wire", "magazine")
        ):
            countries = [scountry]
        # una institución nacional (Casa Blanca, BOE, Fed) habla ante todo de su país: va primero
        if national_source and doc["stype"] in ("institution", "central_bank", "court", "statistical_office"):
            countries = [scountry] + [c for c in countries if c != scountry]
        vec = emb.embed(text_for_embedding, extra_tokens=keys + [f"topic:{t}" for t in topics])
        domain = classify_domain(f"{doc['title']} {doc['lede'] or ''}")
        event_id, sim, created = idx.assign(
            doc["id"],
            vec,
            keys,
            countries,
            doc["published_at"],
            domain,
            doc["title"],
            topics,
            source_id=doc["source_id"],
        )
        stats["new_events" if created else "joined"] += 1
        touched.add(event_id)
        with db.tx() as conn:
            conn.execute(
                "UPDATE document SET embedding = ?, embedding_model = ?, countries = ?, event_id = ? WHERE id = ?",
                (vec_to_blob(vec), emb.name, dumps(countries), event_id, doc["id"]),
            )
            conn.execute(
                "INSERT OR IGNORE INTO event_document(event_id, document_id, similarity) VALUES (?,?,?)",
                (event_id, doc["id"], round(sim, 3)),
            )
            for m in mentions[:12]:
                eid = ent_cache.get(m.key)
                if eid is None and m.kind == "topic":
                    eid = new_id()
                    conn.execute(
                        "INSERT INTO entity(id, kind, name, aliases, attributes, created_at) VALUES (?,?,?,?,?,?)",
                        (eid, "concept", m.name, dumps([]), dumps({"key": m.key}), now_iso()),
                    )
                    ent_cache[m.key] = eid
                if eid:
                    conn.execute(
                        "INSERT OR IGNORE INTO document_entity(document_id, entity_id, salience) VALUES (?,?,?)",
                        (doc["id"], eid, min(1.0, m.count / 10.0)),
                    )
        # afirmaciones
        cands = None
        if llm is not None and (doc["tier"] or 4) <= 3:
            try:
                from .agents import extract_claims_llm

                cands = extract_claims_llm(db, doc, source, llm)
                stats["llm_docs"] += 1
            except (LLMUnavailable, BudgetExceeded):
                llm = None
            except Exception:  # noqa: BLE001 - el heurístico es el respaldo
                cands = None
        if cands is None:
            cands = heuristic_claims(doc, source)
        cs = persist_claims(db, doc, source, event_id, cands)
        stats["claims_new"] += cs["new"]
        stats["claims_merged"] += cs["merged"]
        stats["claims_dropped"] += cs["dropped"]
    created, updated = idx.flush()
    stats["events_created"] = created
    stats["events_updated"] = updated
    stats["touched"] = len(touched)
    # motores por evento
    shares = baseline_shares(db)
    n_deltas = 0
    n_alerts = 0
    for eid in touched:
        compute_coverage(db, eid, shares)
        compute_materiality(db, eid)
        n_deltas += deltas_from_event(db, eid)
        n_alerts += len(evaluate_event(db, eid))
    stats["state_deltas"] = n_deltas
    stats["exposure_alerts"] = n_alerts
    # títulos neutros con LLM para eventos relevantes
    if llm is not None:
        from .agents import neutral_title

        n_titles = 0
        for eid in touched:
            ev = db.one("SELECT n_docs, materiality, title_source FROM event WHERE id = ?", (eid,))
            if ev and ev["n_docs"] >= 3 and (ev["materiality"] or 0) >= 40 and ev["title_source"] != "llm":
                try:
                    if neutral_title(db, eid, llm):
                        n_titles += 1
                except Exception:  # noqa: BLE001
                    break
        stats["llm_titles"] = n_titles
    return stats


def recompute_events(db: Database, hours: int = 72) -> dict[str, int]:
    """Consolida duplicados y recalcula cobertura y materialidad de los eventos activos (la novedad decae,
    las cuotas de producción cambian)."""
    cons = consolidate_events(db, hours=min(hours, 48))
    ids = [
        r["id"]
        for r in db.all(
            "SELECT id FROM event WHERE status != 'merged' AND last_update_at >= datetime('now', ?)",
            (f"-{hours} hours",),
        )
    ]
    shares = baseline_shares(db)
    for eid in ids:
        compute_coverage(db, eid, shares)
        compute_materiality(db, eid)
    return {"events": len(ids), "consolidated": cons.get("merged", 0)}


async def run_ingest(
    db: Database, force: bool = False, limit_sources: int | None = None, use_llm: bool | None = None
) -> dict[str, Any]:
    job = _job_start(db, "ingest")
    t0 = time.monotonic()
    try:
        sources = due_sources(db, force=force, limit=limit_sources)
        fetch_stats = await fetch_sources(db, sources)
        # CPU-bound: fuera del bucle de eventos para que la API siga respondiendo durante el procesado
        proc_stats = await asyncio.to_thread(process_new_documents, db, use_llm=use_llm)
        stats = {"fetch": fetch_stats, "process": proc_stats, "seconds": round(time.monotonic() - t0, 1)}
        _job_end(db, job, True, stats)
        return stats
    except Exception as e:  # noqa: BLE001
        _job_end(db, job, False, {"seconds": round(time.monotonic() - t0, 1)}, f"{type(e).__name__}: {e}")
        raise


async def run_markets(db: Database) -> dict[str, Any]:
    job = _job_start(db, "markets")
    try:
        async with make_client(timeout=20.0) as client:
            mk = await refresh_markets(db, client)
            pm = await refresh_prediction_markets(db, client)
        deltas = deltas_from_markets(db)
        stats = {"markets": mk, "prediction_markets": pm, "fx_deltas": deltas}
        _job_end(db, job, True, stats)
        return stats
    except Exception as e:  # noqa: BLE001
        _job_end(db, job, False, {}, f"{type(e).__name__}: {e}")
        raise


def event_summary_row(db: Database, row) -> dict[str, Any]:
    d = dict(row)
    for f in ("countries", "entity_keys"):
        d[f] = loads(d.get(f), [])
    for f in ("materiality_breakdown", "coverage_stats", "silence_index", "geo"):
        d[f] = loads(d.get(f), None)
    d.pop("centroid", None)
    return d
