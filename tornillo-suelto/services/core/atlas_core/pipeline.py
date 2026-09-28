"""Pipeline de ingesta (docs/spec/01 §4):

fuente → conector.fetch() → documento → deduplicación → embedding → entidades (gazetteer) → evento (clustering)
→ afirmaciones con cita → cobertura y silencio → materialidad → deltas de estado → exposición (MANDO).
Con clave de API y presupuesto: extractor Haiku para las fuentes de tier ≤ 3 y títulos neutros para eventos con
≥ 3 documentos.
"""

from __future__ import annotations

import asyncio
import fcntl
import logging
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

from .connectors.base import make_client
from .connectors.markets import refresh_markets
from .connectors.prediction_markets import refresh_prediction_markets
from .connectors.rss import RSSConnector, resolve_link
from .db import Database, dumps, loads, new_id, now_iso, row_to_dict, since_iso, vec_to_blob
from .embed import IDF, get_embedder, set_idf
from .engines.claims import compute_status, heuristic_claims, persist_claims
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
from .util import canonicalize_url, parse_iso

log = logging.getLogger("atlas.pipeline")

MAX_ITEMS_PER_SOURCE_PER_RUN = 60
MAX_ITEMS_BULLETIN = 40  # boletines oficiales y agencias muy prolíficas
# published_at no puede ser posterior a la descarga: tolerancia de reloj antes de acotarlo
PUBLISHED_AT_SKEW = timedelta(minutes=15)
BUSY_REASON = "otra pasada en curso"


class JobBusy(Exception):
    """Ya hay una pasada de ingesta/recálculo sobre esta base de datos (otro hilo u otro proceso)."""


_memory_locks: dict[str, threading.Lock] = {}


@contextmanager
def job_lock(db: Database, job: str = "ingest") -> Iterator[None]:
    """Exclusión mutua entre hilos Y procesos para las pasadas que escriben eventos (ingesta y recálculo).

    `flock` sobre `<db>.<job>.lock`: el cerrojo va ligado a la descripción de fichero abierta, así que dos
    hilos del mismo proceso (planificador vs API) o dos procesos (`atlas ingest` vs servidor) sobre el mismo
    atlas.db se excluyen igual. Sin él, dos `process_new_documents` a la vez ven los mismos documentos sin evento
    y cada uno crea sus propios eventos y afirmaciones (eventos gemelos, afirmaciones duplicadas). No bloquea:
    si el cerrojo está ocupado lanza JobBusy y el llamador devuelve {'started': False, ...}.
    """
    if str(db.path) == ":memory:":
        lock = _memory_locks.setdefault(job, threading.Lock())
        if not lock.acquire(blocking=False):
            raise JobBusy(job)
        try:
            yield
        finally:
            lock.release()
        return
    path = Path(f"{db.path}.{job}.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = path.open("a+")
    try:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise JobBusy(job) from None
        yield
    finally:
        fh.close()  # cerrar el descriptor libera el flock


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


def _record_health(
    db: Database,
    src: dict[str, Any],
    ts: str,
    ok: bool,
    n_items: int,
    error: str | None,
    latency_ms: int | None,
    etag: str | None = None,
    last_modified: str | None = None,
) -> None:
    """Fila en source_health Y actualización de `source`: `last_polled_at` se fija siempre (también al fallar),
    si no la fuente rota sigue siendo «due» y se reintenta en cada ciclo."""
    with db.tx() as c:
        c.execute(
            "INSERT INTO source_health(source_id, checked_at, ok, items, error, latency_ms) VALUES (?,?,?,?,?,?)",
            (src["id"], ts, 1 if ok else 0, n_items, error, latency_ms),
        )
        fields: dict[str, Any] = {"last_polled_at": ts, "last_error": error}
        if ok:
            fields.update({"last_ok_at": ts, "last_items": n_items})
            if etag:
                fields["etag"] = etag
            if last_modified:
                fields["last_modified"] = last_modified
        sets = ", ".join(f"{k} = ?" for k in fields)
        c.execute(f"UPDATE source SET {sets} WHERE id = ?", (*fields.values(), src["id"]))


def _normalize_and_insert(
    db: Database, conn_rss: RSSConnector, src: dict[str, Any], items: list
) -> tuple[int, int]:
    return insert_documents(db, src, [conn_rss.normalize(src, it) for it in items])


async def fetch_sources(db: Database, sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Descarga feeds en paralelo, registra salud e inserta documentos nuevos.

    Cada fuente está aislada: un fallo (URL inválida, timeout total, BD bloqueada...) se anota en su salud y en
    stats['errors'] y NUNCA aborta la pasada de las demás. Parseo, normalización e inserción van a un hilo para
    que el bucle de eventos siga sirviendo la API."""
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
        t0 = time.monotonic()
        try:
            async with sem:
                # plazo TOTAL por fuente: el timeout de httpx es por fragmento y un servidor que gotea nunca lo agota
                async with asyncio.timeout(settings.atlas_source_timeout):
                    res = await conn_rss.fetch(src, client)
            ts = now_iso()
            _record_health(
                db, src, ts, res.ok, len(res.items), res.error, res.latency_ms, res.etag, res.last_modified
            )
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
            new, dup = await asyncio.to_thread(_normalize_and_insert, db, conn_rss, src, res.items[:cap])
            stats["new_docs"] += new
            stats["dup_docs"] += dup
        except Exception as e:  # noqa: BLE001 - una fuente rota no tumba la ingesta
            err = f"{type(e).__name__}: {e}"[:200]
            stats["failed"] += 1
            stats["errors"].append(f"{src['slug']}: {err}"[:120])
            try:
                _record_health(db, src, now_iso(), False, 0, err, int((time.monotonic() - t0) * 1000))
            except Exception as e2:  # noqa: BLE001 - p. ej. BD bloqueada: queda constancia en job_run.stats
                stats["errors"].append(f"{src['slug']}: salud no registrada: {type(e2).__name__}"[:120])
                log.warning("source_health %s: %s", src.get("slug"), e2)

    async with make_client() as client:
        await asyncio.gather(*(one(s, client) for s in sources))
    return stats


def insert_documents(db: Database, source: dict[str, Any], docs: list) -> tuple[int, int]:
    """Inserta documentos nuevos; deduplica por url, canonical_url y (content_hash, fuente). La comprobación va
    en la MISMA transacción que el INSERT (url es UNIQUE: dos fuentes o dos entradas con la misma URL en vuelo
    no deben abortar la pasada); con ix_document_canonical cuesta microsegundos."""
    new = dup = 0
    ts = now_iso()
    fetched = parse_iso(ts)
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
            published_at = d.published_at or ts
            meta = dict(d.meta or {})
            pub = parse_iso(d.published_at) if d.published_at else None
            if pub and fetched and pub > fetched + PUBLISHED_AT_SKEW:
                # hora local publicada sin zona y tomada como UTC: quedaría «activo» y en cabeza más de lo debido
                meta["published_at_reported"] = d.published_at
                published_at = (fetched + PUBLISHED_AT_SKEW).isoformat()
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
                    published_at,
                    ts,
                    d.content_hash,
                    d.extraction_method,
                    1 if d.paywalled else 0,
                    dumps(meta),
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
    total["claims_deduplicated"] = 0
    for eid in cons.get("winners", []) or []:
        total["claims_deduplicated"] += dedup_event_claims(db, eid)
        compute_coverage(db, eid)
        compute_materiality(db, eid)
        deltas_from_event(db, eid)
        evaluate_event(db, eid)
    return total


def dedup_event_claims(db: Database, event_id: str) -> int:
    """Tras fusionar eventos, una misma afirmación (document_id, text_canonical) puede estar repetida en el
    ganador: consolidate_events solo reasigna `claim.event_id`. Se conserva la más antigua; la evidencia de las
    demás pasa a ella (salvo la ya presente para ese documento), las repetidas salen del evento con
    `status='merged'` y todo queda en claim_revision (nunca se borra historia). Devuelve nº de fusionadas."""
    rows = db.all(
        "SELECT id, document_id, text_canonical, status FROM claim WHERE event_id = ? ORDER BY created_at ASC, id ASC",
        (event_id,),
    )
    groups: dict[tuple[str, str], list[Any]] = {}
    for r in rows:
        groups.setdefault((r["document_id"], r["text_canonical"]), []).append(r)
    merged = 0
    ts = now_iso()
    with db.tx() as conn:
        for items in groups.values():
            if len(items) < 2:
                continue
            keeper = items[0]
            for dup in items[1:]:
                moved = []
                for ev in conn.execute(
                    "SELECT id, document_id FROM claim_evidence WHERE claim_id = ?", (dup["id"],)
                ).fetchall():
                    present = conn.execute(
                        "SELECT 1 FROM claim_evidence WHERE claim_id = ? AND document_id = ?",
                        (keeper["id"], ev["document_id"]),
                    ).fetchone()
                    if present:
                        continue  # la copia idéntica se queda colgando de la afirmación fusionada
                    conn.execute(
                        "UPDATE claim_evidence SET claim_id = ? WHERE id = ?", (keeper["id"], ev["id"])
                    )
                    moved.append(ev["id"])
                conn.execute("UPDATE claim SET status = 'merged', event_id = NULL WHERE id = ?", (dup["id"],))
                conn.execute(
                    "INSERT INTO claim_revision(id, claim_id, old_status, new_status, reason, evidence_ids, changed_at) VALUES (?,?,?,?,?,?,?)",
                    (
                        new_id(),
                        dup["id"],
                        dup["status"],
                        "merged",
                        f"duplicada de {keeper['id']} (misma afirmación y documento tras fusión de eventos)",
                        dumps(moved),
                        ts,
                    ),
                )
                merged += 1
            ev_rows = [
                dict(r)
                for r in conn.execute(
                    """SELECT ce.stance, ce.quote, d.source_id, s.tier FROM claim_evidence ce
                       JOIN document d ON d.id = ce.document_id JOIN source s ON s.id = d.source_id
                       WHERE ce.claim_id = ?""",
                    (keeper["id"],),
                ).fetchall()
            ]
            new_status = compute_status(ev_rows)
            if new_status != keeper["status"]:
                conn.execute("UPDATE claim SET status = ? WHERE id = ?", (new_status, keeper["id"]))
                conn.execute(
                    "INSERT INTO claim_revision(id, claim_id, old_status, new_status, reason, evidence_ids, changed_at) VALUES (?,?,?,?,?,?,?)",
                    (
                        new_id(),
                        keeper["id"],
                        keeper["status"],
                        new_status,
                        f"{len(ev_rows)} evidencias tras fusionar afirmaciones duplicadas",
                        dumps([]),
                        ts,
                    ),
                )
    return merged


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
            if (
                ev
                and ev["n_docs"] >= 3
                and (ev["materiality"] or 0) >= 40
                and ev["title_source"] not in ("llm", "llm_unverified")
            ):
                try:
                    if neutral_title(db, eid, llm):
                        n_titles += 1
                except Exception:  # noqa: BLE001
                    break
        stats["llm_titles"] = n_titles
    return stats


def recompute_events(db: Database, hours: int = 72) -> dict[str, Any]:
    """Consolida duplicados y recalcula cobertura y materialidad de los eventos activos (la novedad decae,
    las cuotas de producción cambian). Comparte cerrojo con la ingesta: consolidar mientras otro ClusterIndex
    está en memoria dejaría documentos asignados a eventos ya `merged`."""
    try:
        with job_lock(db):
            cons = consolidate_events(db, hours=min(hours, 48))
            for eid in cons.get("winners", []) or []:
                dedup_event_claims(db, eid)
            ids = [
                r["id"]
                for r in db.all(
                    "SELECT id FROM event WHERE status != 'merged' AND last_update_at >= ?",
                    (since_iso(hours=hours),),
                )
            ]
            shares = baseline_shares(db)
            for eid in ids:
                compute_coverage(db, eid, shares)
                compute_materiality(db, eid)
            return {"events": len(ids), "consolidated": cons.get("merged", 0)}
    except JobBusy:
        return {"events": 0, "consolidated": 0, "started": False, "reason": BUSY_REASON}


async def run_ingest(
    db: Database, force: bool = False, limit_sources: int | None = None, use_llm: bool | None = None
) -> dict[str, Any]:
    job = _job_start(db, "ingest")
    t0 = time.monotonic()
    try:
        with job_lock(db):
            sources = due_sources(db, force=force, limit=limit_sources)
            fetch_stats = await fetch_sources(db, sources)
            # CPU-bound: fuera del bucle de eventos para que la API siga respondiendo durante el procesado
            proc_stats = await asyncio.to_thread(process_new_documents, db, use_llm=use_llm)
            stats = {"fetch": fetch_stats, "process": proc_stats, "seconds": round(time.monotonic() - t0, 1)}
            _job_end(db, job, True, stats)
            return stats
    except JobBusy:
        _job_end(db, job, False, {"skipped": True}, BUSY_REASON)
        return {"started": False, "reason": BUSY_REASON}
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


def _merge_document_into(db: Database, dup_id: str, keep_id: str) -> None:
    """Fusiona el documento `dup_id` en `keep_id` (misma URL absoluta): mueve entidades, pertenencia a evento,
    afirmaciones, evidencias, lecturas y deltas; solo entonces se elimina la fila duplicada."""
    with db.tx() as conn:
        dup = conn.execute("SELECT event_id FROM document WHERE id = ?", (dup_id,)).fetchone()
        keep = conn.execute("SELECT event_id FROM document WHERE id = ?", (keep_id,)).fetchone()
        conn.execute(
            "INSERT OR IGNORE INTO document_entity(document_id, entity_id, salience) SELECT ?, entity_id, salience FROM document_entity WHERE document_id = ?",
            (keep_id, dup_id),
        )
        conn.execute("DELETE FROM document_entity WHERE document_id = ?", (dup_id,))
        conn.execute(
            "INSERT OR IGNORE INTO event_document(event_id, document_id, similarity) SELECT event_id, ?, similarity FROM event_document WHERE document_id = ?",
            (keep_id, dup_id),
        )
        conn.execute("DELETE FROM event_document WHERE document_id = ?", (dup_id,))
        for table, col in (
            ("claim", "document_id"),
            ("claim_evidence", "document_id"),
            ("reading_log", "document_id"),
            ("state_delta", "source_doc_id"),
            ("state_observation", "source_doc_id"),
        ):
            conn.execute(f"UPDATE {table} SET {col} = ? WHERE {col} = ?", (keep_id, dup_id))
        conn.execute("UPDATE event SET lead_document_id = ? WHERE lead_document_id = ?", (keep_id, dup_id))
        if keep and dup and keep["event_id"] is None and dup["event_id"]:
            conn.execute("UPDATE document SET event_id = ? WHERE id = ?", (dup["event_id"], keep_id))
        conn.execute("DELETE FROM document_fts WHERE doc_id = ?", (dup_id,))
        conn.execute("DELETE FROM document WHERE id = ?", (dup_id,))
        for ev in {dup["event_id"] if dup else None, keep["event_id"] if keep else None} - {None}:
            conn.execute(
                "UPDATE event SET n_docs = (SELECT COUNT(*) FROM document WHERE event_id = ?) WHERE id = ?",
                (ev, ev),
            )
    for ev in {dup["event_id"] if dup else None, keep["event_id"] if keep else None} - {None}:
        dedup_event_claims(db, ev)


def repair_relative_urls(db: Database, apply: bool = False) -> dict[str, Any]:
    """Reparación única de documentos guardados con enlace relativo ('/article/x', 'www.bea.gov/...') antes de
    que el conector resolviera los enlaces: se resuelven contra el feed guardado en meta.feed (o el dominio de
    la fuente). Si la URL absoluta ya existe (reingesta posterior), el duplicado se fusiona con
    `_merge_document_into`, nunca con un DELETE ciego. Con apply=False solo cuenta."""
    rows = db.all(
        """SELECT d.id, d.url, d.meta, s.domain FROM document d JOIN source s ON s.id = d.source_id
           WHERE d.url NOT LIKE 'http://%' AND d.url NOT LIKE 'https://%'"""
    )
    out = {"candidates": len(rows), "fixed": 0, "merged": 0, "unresolved": 0, "applied": apply}
    for r in rows:
        feed = (loads(r["meta"], {}) or {}).get("feed") or (f"https://{r['domain']}/" if r["domain"] else "")
        new_url = resolve_link(r["url"], feed, r["domain"]) if feed else None
        if not new_url:
            out["unresolved"] += 1
            continue
        other = db.one("SELECT id FROM document WHERE url = ? AND id != ?", (new_url, r["id"]))
        if other:
            out["merged"] += 1
            if apply:
                _merge_document_into(db, r["id"], other["id"])
            continue
        out["fixed"] += 1
        if apply:
            with db.tx() as conn:
                conn.execute(
                    "UPDATE document SET url = ?, canonical_url = ? WHERE id = ?",
                    (new_url, canonicalize_url(new_url), r["id"]),
                )
    return out


def event_summary_row(db: Database, row) -> dict[str, Any]:
    d = dict(row)
    for f in ("countries", "entity_keys"):
        d[f] = loads(d.get(f), [])
    for f in ("materiality_breakdown", "coverage_stats", "silence_index", "geo"):
        d[f] = loads(d.get(f), None)
    d.pop("centroid", None)
    return d
