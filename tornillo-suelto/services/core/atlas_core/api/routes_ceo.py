"""Modo CEO y transversales: MANDO, DIETA, BRIEF, SALA DE MÁQUINAS, alertas, ajustes, búsqueda."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from ..config_loader import profile_config
from ..db import dumps, loads, new_id, now_iso
from ..engines.brief import compose_brief
from ..engines.diet import diet_report
from ..engines.exposure import EU_MEMBERS
from ..llm import get_llm
from ..pipeline import recompute_events, run_ingest, run_markets
from .deps import db, doc_out, event_out

router = APIRouter()

# ───────────── MANDO ─────────────


@router.get("/mando")
def mando() -> dict[str, Any]:
    d = db()
    businesses = []
    for b in d.all("SELECT * FROM business_unit"):
        x = dict(b)
        for f in ("sectors", "jurisdictions", "markets", "currencies", "regulations", "keywords"):
            x[f] = loads(x[f], [])
        x["alerts_7d"] = d.scalar("SELECT COUNT(*) FROM exposure_alert WHERE business_id = ? AND dismissed = 0 AND created_at >= datetime('now','-7 days')", (x["id"],), 0)
        businesses.append(x)
    alerts = []
    for r in d.all(
        """SELECT ea.*, b.name AS business_name, e.title_neutral, e.materiality, e.countries, e.domain FROM exposure_alert ea
           JOIN business_unit b ON b.id = ea.business_id JOIN event e ON e.id = ea.event_id
           WHERE ea.dismissed = 0 ORDER BY ea.confidence DESC, ea.created_at DESC LIMIT 60"""
    ):
        a = dict(r)
        a["countries"] = loads(a["countries"], [])
        alerts.append(a)
    decisions = []
    for r in d.all("SELECT dl.*, b.name AS business_name FROM decision_log dl LEFT JOIN business_unit b ON b.id = dl.business_id ORDER BY decided_at DESC"):
        x = dict(r)
        x["premises"] = loads(x["premises"], [])
        x["alternatives"] = loads(x["alternatives"], [])
        decisions.append(x)
    juris: set[str] = set()
    regs: list[str] = []
    for b in businesses:
        juris |= set(b["jurisdictions"])
        regs += b["regulations"]
    countries = set(juris)
    if "EU" in juris:
        countries |= EU_MEMBERS
    reg_docs = []
    if countries:
        marks = ",".join("?" for _ in countries)
        rows = d.all(
            f"""SELECT d.*, s.name AS source_name, s.country AS source_country, s.type AS source_type FROM document d JOIN source s ON s.id = d.source_id
                WHERE s.tier = 1 AND (s.country IN ({marks}) OR s.country = 'EU') AND d.fetched_at >= datetime('now','-14 days') ORDER BY d.published_at DESC LIMIT 300""",
            list(countries),
        )
        from ..embed import normalize_text

        terms = [normalize_text(r.split("(")[0].strip()) for r in regs if r] + ["ai act", "ehds", "mdr", "rgpd", "gdpr", "complementos alimenticios", "productos sanitarios", "ensayos clínicos", "salud digital", "datos de salud", "formación profesional", "impuesto de sociedades", "fiscalidad"]
        terms = [t for t in terms if t]
        for r in rows:
            blob = normalize_text(f"{r['title']} {r['lede'] or ''}")
            hits = [t for t in terms if t in blob]
            if hits:
                x = doc_out(r)
                x["hits"] = hits
                reg_docs.append(x)
            if len(reg_docs) >= 40:
                break
    return {"businesses": businesses, "alerts": alerts, "decisions": decisions, "regulatory": reg_docs, "profile_note": "Los negocios se cargan de config/perfil.yaml y no salen de esta máquina."}


@router.post("/mando/alerts/{alert_id}/dismiss")
def dismiss_alert(alert_id: str) -> dict[str, Any]:
    d = db()
    with d.tx() as conn:
        conn.execute("UPDATE exposure_alert SET dismissed = 1 WHERE id = ?", (alert_id,))
    return {"ok": True}


class DecisionIn(BaseModel):
    business_id: str | None = None
    title: str
    context: str | None = None
    premises: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    success_probability: float | None = Field(default=None, ge=0, le=1)
    premortem: str | None = None
    review_at: str | None = None


@router.post("/mando/decisions")
def create_decision(body: DecisionIn) -> dict[str, Any]:
    d = db()
    did = new_id()
    with d.tx() as conn:
        conn.execute(
            """INSERT INTO decision_log(id, business_id, title, context, premises, alternatives, success_probability, premortem, decided_at, review_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (did, body.business_id, body.title, body.context, dumps(body.premises), dumps(body.alternatives), body.success_probability, body.premortem, now_iso(), body.review_at),
        )
    return {"id": did}


class DecisionOutcome(BaseModel):
    outcome: str
    lessons: str | None = None


@router.post("/mando/decisions/{decision_id}/outcome")
def decision_outcome(decision_id: str, body: DecisionOutcome) -> dict[str, Any]:
    d = db()
    d.update("decision_log", decision_id, {"outcome": body.outcome, "lessons": body.lessons})
    return {"ok": True}


# ───────────── DIETA ─────────────


class LogIn(BaseModel):
    document_id: str | None = None
    event_id: str | None = None
    action: str = "open"
    seconds: int = 0
    topic: str | None = None


@router.post("/diet/log")
def diet_log(body: LogIn) -> dict[str, Any]:
    d = db()
    source_id = None
    topic = body.topic
    if body.document_id:
        r = d.one("SELECT source_id, event_id FROM document WHERE id = ?", (body.document_id,))
        if r:
            source_id = r["source_id"]
            body.event_id = body.event_id or r["event_id"]
    if not topic and body.event_id:
        ev = d.one("SELECT coverage_stats, domain FROM event WHERE id = ?", (body.event_id,))
        if ev:
            topics = (loads(ev["coverage_stats"], {}) or {}).get("topics") or []
            topic = topics[0] if topics else ev["domain"]
    with d.tx() as conn:
        conn.execute("INSERT INTO reading_log(document_id, event_id, source_id, action, seconds, at, topic) VALUES (?,?,?,?,?,?,?)", (body.document_id, body.event_id, source_id, body.action, body.seconds, now_iso(), topic))
    return {"ok": True}


@router.get("/diet/report")
def diet(days: int = 7) -> dict[str, Any]:
    return diet_report(db(), days=days)


# ───────────── BRIEF ─────────────


@router.get("/brief/latest")
def brief_latest(kind: str = "study") -> dict[str, Any]:
    d = db()
    r = d.one("SELECT * FROM brief WHERE kind = ? ORDER BY created_at DESC LIMIT 1", (kind,))
    if not r:
        return {"brief": None}
    c = loads(r["content"], {})
    c["id"] = r["id"]
    c["composed_by"] = r["composed_by"]
    c["created_at"] = r["created_at"]
    history = [dict(x) for x in d.all("SELECT id, date, kind, composed_by, created_at FROM brief ORDER BY created_at DESC LIMIT 30")]
    return {"brief": c, "history": history}


@router.get("/brief/{brief_id}")
def brief_get(brief_id: str) -> dict[str, Any]:
    d = db()
    r = d.one("SELECT * FROM brief WHERE id = ?", (brief_id,))
    if not r:
        raise HTTPException(404, "brief no encontrado")
    c = loads(r["content"], {})
    c["id"] = r["id"]
    c["composed_by"] = r["composed_by"]
    c["created_at"] = r["created_at"]
    return {"brief": c}


@router.post("/brief/generate")
def brief_generate(kind: str = "study", hours: int = 24) -> dict[str, Any]:
    return {"brief": compose_brief(db(), kind=kind, hours=hours)}


# ───────────── SALA DE MÁQUINAS ─────────────


@router.get("/machine")
def machine() -> dict[str, Any]:
    d = db()
    sources = [dict(r) for r in d.all(
        """SELECT id, slug, name, tier, type, country, region_bloc, active, feeds, feed_status, poll_minutes, last_polled_at, last_ok_at, last_error, last_items,
                  (SELECT COUNT(*) FROM document WHERE document.source_id = source.id AND fetched_at >= datetime('now','-1 day')) AS docs_24h
           FROM source ORDER BY active DESC, tier, name"""
    )]
    for s in sources:
        s["feeds"] = loads(s["feeds"], [])
    jobs = [dict(r) for r in d.all("SELECT * FROM job_run ORDER BY id DESC LIMIT 40")]
    for j in jobs:
        j["stats"] = loads(j["stats"], {})
    llm = get_llm(d)
    cost_by_day = [dict(r) for r in d.all("SELECT substr(at,1,10) AS day, module, model, COUNT(*) n, SUM(cost_usd) cost, SUM(input_tokens) input_tokens, SUM(output_tokens) output_tokens, SUM(cache_read_tokens) cache_read FROM llm_call GROUP BY day, module, model ORDER BY day DESC LIMIT 200")]
    recent_calls = [dict(r) for r in d.all("SELECT id, at, module, agent, model, input_tokens, output_tokens, cache_read_tokens, cost_usd, latency_ms, ok, error FROM llm_call ORDER BY id DESC LIMIT 30")]
    totals = {
        "sources_total": len(sources),
        "sources_active": sum(1 for s in sources if s["active"]),
        "sources_with_feed": sum(1 for s in sources if s["feeds"]),
        "sources_ok_24h": sum(1 for s in sources if s["last_ok_at"] and s["last_ok_at"] >= (now_iso()[:10])),
        "documents": d.scalar("SELECT COUNT(*) FROM document", (), 0),
        "documents_24h": d.scalar("SELECT COUNT(*) FROM document WHERE fetched_at >= datetime('now','-1 day')", (), 0),
        "events": d.scalar("SELECT COUNT(*) FROM event WHERE status != 'merged'", (), 0),
        "claims": d.scalar("SELECT COUNT(*) FROM claim", (), 0),
        "claims_confirmed": d.scalar("SELECT COUNT(*) FROM claim WHERE status = 'confirmed'", (), 0),
        "db_size_mb": round((d.path.stat().st_size / 1e6) if d.path.exists() else 0, 1),
    }
    return {"sources": sources, "jobs": jobs, "budget": llm.budget_state(), "llm_cost": cost_by_day, "llm_recent": recent_calls, "totals": totals, "embedder": __import__("atlas_core.embed", fromlist=["get_embedder"]).get_embedder().name}


_running: dict[str, bool] = {}


async def _bg(job: str, coro) -> None:
    if _running.get(job):
        return
    _running[job] = True
    try:
        await coro
    except Exception:  # noqa: BLE001 - queda en job_run
        pass
    finally:
        _running[job] = False


@router.post("/machine/ingest")
async def trigger_ingest(background: BackgroundTasks, force: bool = False, limit: int | None = None) -> dict[str, Any]:
    if _running.get("ingest"):
        return {"started": False, "reason": "ya hay una ingesta en curso"}
    background.add_task(_bg, "ingest", run_ingest(db(), force=force, limit_sources=limit))
    return {"started": True}


@router.post("/machine/markets")
async def trigger_markets(background: BackgroundTasks) -> dict[str, Any]:
    if _running.get("markets"):
        return {"started": False, "reason": "ya hay una actualización en curso"}
    background.add_task(_bg, "markets", run_markets(db()))
    return {"started": True}


@router.post("/machine/recompute")
def trigger_recompute(hours: int = 72) -> dict[str, Any]:
    return recompute_events(db(), hours=hours)


@router.post("/machine/sources/{source_id}/toggle")
def toggle_source(source_id: str) -> dict[str, Any]:
    d = db()
    r = d.one("SELECT active FROM source WHERE id = ?", (source_id,))
    if not r:
        raise HTTPException(404, "fuente no encontrada")
    with d.tx() as conn:
        conn.execute("UPDATE source SET active = ? WHERE id = ?", (0 if r["active"] else 1, source_id))
    return {"active": 0 if r["active"] else 1}


@router.get("/machine/running")
def running() -> dict[str, Any]:
    return {k: v for k, v in _running.items()}


# ───────────── ALERTAS, AJUSTES, BÚSQUEDA ─────────────


@router.get("/alerts")
def alerts() -> dict[str, Any]:
    d = db()
    rows = [dict(r) for r in d.all("SELECT * FROM alert ORDER BY created_at DESC LIMIT 50")]
    for r in rows:
        r["ref"] = loads(r["ref"], {})
    high = [event_out(r) for r in d.all("SELECT * FROM event WHERE materiality >= 80 AND last_update_at >= datetime('now','-1 day') ORDER BY materiality DESC LIMIT 10")]
    return {"alerts": rows, "high_materiality": high, "unread": sum(1 for r in rows if not r["read"])}


@router.post("/alerts/read")
def alerts_read() -> dict[str, Any]:
    d = db()
    with d.tx() as conn:
        conn.execute("UPDATE alert SET read = 1")
    return {"ok": True}


@router.get("/settings")
def get_settings() -> dict[str, Any]:
    d = db()
    prof = profile_config().get("preferencias_atlas", {}) or {}
    defaults = {"theme": "light" if prof.get("tema") != "oscuro" else "dark", "mode": prof.get("modo_inicio", "ANALISTA"), "cat_enabled": True, "density": "compact", "brief_hour": profile_config().get("usuario", {}).get("hora_brief", "07:00")}
    stored = d.get_setting("ui", {}) or {}
    return {**defaults, **stored}


@router.put("/settings")
def put_settings(body: dict[str, Any]) -> dict[str, Any]:
    d = db()
    current = d.get_setting("ui", {}) or {}
    current.update({k: v for k, v in body.items() if k in ("theme", "mode", "cat_enabled", "density", "brief_hour")})
    with d.tx():
        d.set_setting("ui", current)
    return current


@router.get("/search")
def search(q: str, limit: int = 8) -> dict[str, Any]:
    d = db()
    q = q.strip()
    if not q:
        return {"events": [], "documents": [], "entities": [], "notes": [], "questions": [], "cases": [], "countries": []}
    like = f"%{q}%"
    events = [event_out(r) for r in d.all("SELECT * FROM event WHERE status != 'merged' AND title_neutral LIKE ? ORDER BY last_update_at DESC LIMIT ?", (like, limit))]
    docs = []
    try:
        fts_q = " ".join(f'"{t}"' for t in q.replace('"', "").split()[:6])
        docs = [doc_out(r) for r in d.all(
            """SELECT d.*, s.name AS source_name, s.tier FROM document_fts f JOIN document d ON d.id = f.doc_id JOIN source s ON s.id = d.source_id
               WHERE document_fts MATCH ? ORDER BY bm25(document_fts) LIMIT ?""",
            (fts_q, limit),
        )]
    except Exception:  # noqa: BLE001 - consulta FTS malformada
        docs = []
    entities = [dict(r) for r in d.all("SELECT id, kind, name, country FROM entity WHERE name LIKE ? OR aliases LIKE ? LIMIT ?", (like, f"%{q.lower()}%", limit))]
    notes = [dict(r) for r in d.all("SELECT id, title, updated_at FROM note WHERE title LIKE ? OR body_text LIKE ? LIMIT ?", (like, like, limit))]
    questions = [dict(r) for r in d.all("SELECT id, title, status, close_at FROM forecast_question WHERE title LIKE ? LIMIT ?", (like, limit))]
    cases = [dict(r) for r in d.all("SELECT id, name, category, start_date FROM historical_case WHERE name LIKE ? OR summary LIKE ? LIMIT ?", (like, like, limit))]
    from ..gazetteer import countries as gz

    ql = q.lower()
    countries = [{"iso2": c.iso2, "name": c.name_es} for c in gz().values() if ql in c.name_es.lower() or ql in c.name_en.lower() or ql == c.iso2.lower()][:limit]
    return {"events": events, "documents": docs, "entities": entities, "notes": notes, "questions": questions, "cases": cases, "countries": countries}


__all__ = ["router", "asyncio"]
