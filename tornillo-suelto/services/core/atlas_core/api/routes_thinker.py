"""Modo PENSADOR: ÁGORA (mapas argumentales, genealogía), ARCHIVO, PRONÓSTICOS, TALLER (notas y repaso)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from ..db import dumps, loads, new_id, now_iso
from ..engines import forecast as fmath
from ..engines.archive import analogs, compare_cases
from ..seed_data import GENEALOGY_LIBERTY
from .deps import db, event_out

router = APIRouter()

# ───────────── ÁGORA ─────────────


@router.get("/agora/maps")
def list_maps() -> dict[str, Any]:
    d = db()
    maps = [
        dict(r)
        for r in d.all(
            "SELECT m.*, (SELECT COUNT(*) FROM argument_node n WHERE n.map_id = m.id) AS n_nodes FROM argument_map m ORDER BY created_at"
        )
    ]
    return {"maps": maps}


class MapIn(BaseModel):
    title: str
    topic: str | None = None


@router.post("/agora/maps")
def create_map(body: MapIn) -> dict[str, Any]:
    d = db()
    mid = new_id()
    with d.tx() as conn:
        conn.execute(
            "INSERT INTO argument_map(id, title, topic, created_at) VALUES (?,?,?,?)",
            (mid, body.title, body.topic, now_iso()),
        )
    return {"id": mid}


def _map_analysis(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    """Premisas sin apoyo (premisa/tesis sin ninguna arista de apoyo entrante) y ciclos de apoyo (circularidad)."""
    incoming: dict[str, list[dict[str, Any]]] = {n["id"]: [] for n in nodes}
    for e in edges:
        incoming.setdefault(e["dst"], []).append(e)
    unsupported = [
        n
        for n in nodes
        if n["kind"] in ("thesis", "premise")
        and not any(e["rel"] == "supports" for e in incoming.get(n["id"], []))
    ]
    unanswered = [
        n
        for n in nodes
        if n["kind"] == "objection"
        and not any(e["rel"] in ("replies", "attacks") for e in incoming.get(n["id"], []))
    ]
    adj: dict[str, list[str]] = {}
    for e in edges:
        if e["rel"] == "supports":
            adj.setdefault(e["src"], []).append(e["dst"])
    cycles: list[list[str]] = []
    color: dict[str, int] = {}
    stack: list[str] = []

    def dfs(u: str) -> None:
        color[u] = 1
        stack.append(u)
        for v in adj.get(u, []):
            if color.get(v, 0) == 0:
                dfs(v)
            elif color.get(v) == 1 and v in stack:
                cycles.append(stack[stack.index(v) :] + [v])
        stack.pop()
        color[u] = 2

    for n in nodes:
        if color.get(n["id"], 0) == 0:
            dfs(n["id"])
    return {
        "unsupported": [{"id": n["id"], "text": n["text"][:120]} for n in unsupported],
        "unanswered_objections": [{"id": n["id"], "text": n["text"][:120]} for n in unanswered],
        "support_cycles": cycles[:5],
    }


@router.get("/agora/maps/{map_id}")
def get_map(map_id: str) -> dict[str, Any]:
    d = db()
    m = d.one("SELECT * FROM argument_map WHERE id = ?", (map_id,))
    if not m:
        raise HTTPException(404, "mapa no encontrado")
    nodes = [
        dict(r) for r in d.all("SELECT * FROM argument_node WHERE map_id = ? ORDER BY created_at", (map_id,))
    ]
    edges = [dict(r) for r in d.all("SELECT * FROM argument_edge WHERE map_id = ?", (map_id,))]
    return {"map": dict(m), "nodes": nodes, "edges": edges, "analysis": _map_analysis(nodes, edges)}


class NodeIn(BaseModel):
    kind: str
    text: str
    author: str | None = None
    work: str | None = None
    x: float | None = None
    y: float | None = None


@router.post("/agora/maps/{map_id}/nodes")
def add_node(map_id: str, body: NodeIn) -> dict[str, Any]:
    if body.kind not in ("thesis", "premise", "objection", "reply", "evidence", "author", "work"):
        raise HTTPException(400, "kind inválido")
    d = db()
    nid = new_id()
    with d.tx() as conn:
        conn.execute(
            "INSERT INTO argument_node(id, map_id, kind, text, author, work, is_user, x, y, created_at) VALUES (?,?,?,?,?,?,1,?,?,?)",
            (nid, map_id, body.kind, body.text, body.author, body.work, body.x, body.y, now_iso()),
        )
    return {"id": nid}


class NodeUpdate(BaseModel):
    text: str | None = None
    x: float | None = None
    y: float | None = None
    author: str | None = None
    work: str | None = None


@router.put("/agora/nodes/{node_id}")
def update_node(node_id: str, body: NodeUpdate) -> dict[str, Any]:
    d = db()
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if fields:
        d.update("argument_node", node_id, fields)
    return {"ok": True}


@router.delete("/agora/nodes/{node_id}")
def delete_node(node_id: str) -> dict[str, Any]:
    d = db()
    with d.tx() as conn:
        conn.execute("DELETE FROM argument_edge WHERE src = ? OR dst = ?", (node_id, node_id))
        conn.execute("DELETE FROM argument_node WHERE id = ?", (node_id,))
    return {"ok": True}


class EdgeIn(BaseModel):
    src: str
    dst: str
    rel: str


@router.post("/agora/maps/{map_id}/edges")
def add_edge(map_id: str, body: EdgeIn) -> dict[str, Any]:
    if body.rel not in ("supports", "attacks", "replies", "instantiates"):
        raise HTTPException(400, "rel inválida")
    d = db()
    eid = new_id()
    with d.tx() as conn:
        conn.execute(
            "INSERT INTO argument_edge(id, map_id, src, dst, rel) VALUES (?,?,?,?,?)",
            (eid, map_id, body.src, body.dst, body.rel),
        )
    return {"id": eid}


@router.delete("/agora/edges/{edge_id}")
def delete_edge(edge_id: str) -> dict[str, Any]:
    d = db()
    with d.tx() as conn:
        conn.execute("DELETE FROM argument_edge WHERE id = ?", (edge_id,))
    return {"ok": True}


@router.get("/agora/genealogy")
def genealogy() -> dict[str, Any]:
    return GENEALOGY_LIBERTY


# ───────────── ARCHIVO ─────────────


@router.get("/archive/cases")
def cases(q: str | None = None, category: str | None = None) -> dict[str, Any]:
    d = db()
    sql = "SELECT id, name, category, start_date, end_date, countries, variables, outcome, duration_months, summary, sources FROM historical_case WHERE 1=1"
    params: list[Any] = []
    if q:
        sql += " AND (name LIKE ? OR summary LIKE ? OR outcome LIKE ?)"
        params += [f"%{q}%"] * 3
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY start_date"
    out = []
    for r in d.all(sql, params):
        x = dict(r)
        for f in ("countries", "variables", "sources"):
            x[f] = loads(x[f], [] if f != "variables" else {})
        out.append(x)
    cats = [r["category"] for r in d.all("SELECT DISTINCT category FROM historical_case ORDER BY category")]
    return {"cases": out, "categories": cats}


@router.get("/archive/analogs")
def archive_analogs(
    q: str | None = None, event_id: str | None = None, category: str | None = None, n: int = 4
) -> dict[str, Any]:
    d = db()
    text = q or ""
    if event_id:
        ev = d.one("SELECT title_neutral, domain FROM event WHERE id = ?", (event_id,))
        if ev:
            text = f"{ev['title_neutral']}. {ev['domain']}. {text}"
    if not text.strip():
        raise HTTPException(400, "q o event_id requerido")
    res = analogs(d, text, top_n=n, category=category)
    return {
        "query": text,
        "analogs": res,
        "compare": compare_cases(res) if res else None,
        "note": "Similitud por embeddings locales sobre casos codificados a mano; verificar antes de citar.",
    }


# ───────────── PRONÓSTICOS ─────────────


def _question_out(d, r) -> dict[str, Any]:
    q = dict(r)
    q["countries"] = loads(q["countries"], [])
    q["market_links"] = loads(q["market_links"], [])
    q["options"] = loads(q["options"], None)
    q["outcome"] = loads(q["outcome"], None)
    fc = d.all(
        "SELECT forecaster, probability, rationale, made_at FROM forecast WHERE question_id = ? ORDER BY made_at",
        (q["id"],),
    )
    latest: dict[str, Any] = {}
    series: list[dict[str, Any]] = []
    for f in fc:
        latest[f["forecaster"]] = {"p": f["probability"], "at": f["made_at"], "rationale": f["rationale"]}
        series.append(dict(f))
    q["latest"] = latest
    q["series"] = series
    q["scores"] = [dict(s) for s in d.all("SELECT * FROM forecast_score WHERE question_id = ?", (q["id"],))]
    if q["market_links"]:
        m = d.one(
            "SELECT probability, venue, url, fetched_at FROM prediction_market WHERE id = ?",
            (q["market_links"][0].get("id"),),
        )
        q["market"] = dict(m) if m else None
    else:
        q["market"] = None
    return q


@router.get("/forecasts")
def list_questions(status: str | None = None) -> dict[str, Any]:
    d = db()
    sql = "SELECT * FROM forecast_question"
    params: list[Any] = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY status = 'open' DESC, close_at ASC"
    return {"questions": [_question_out(d, r) for r in d.all(sql, params)]}


class QuestionIn(BaseModel):
    title: str
    resolution_criteria: str
    resolution_source: str | None = None
    close_at: str
    resolve_by: str | None = None
    origin_event_id: str | None = None
    domain: str | None = None
    countries: list[str] = Field(default_factory=list)
    base_rate: float | None = None
    base_rate_note: str | None = None


@router.post("/forecasts")
def create_question(body: QuestionIn) -> dict[str, Any]:
    issues = fmath.question_quality_issues(body.title, body.resolution_criteria, body.base_rate)
    if issues:
        raise HTTPException(422, {"issues": issues})
    d = db()
    qid = new_id()
    with d.tx() as conn:
        conn.execute(
            """INSERT INTO forecast_question(id, title, resolution_criteria, resolution_source, kind, open_at, close_at, resolve_by, origin_event_id, domain, countries, base_rate, base_rate_note, market_links, status, created_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                qid,
                body.title,
                body.resolution_criteria,
                body.resolution_source,
                "binary",
                now_iso(),
                body.close_at,
                body.resolve_by or body.close_at,
                body.origin_event_id,
                body.domain,
                dumps(body.countries),
                body.base_rate,
                body.base_rate_note,
                dumps([]),
                "open",
                "user",
            ),
        )
        if body.base_rate is not None:
            conn.execute(
                "INSERT INTO forecast(id, question_id, forecaster, probability, rationale, made_at) VALUES (?,?,?,?,?,?)",
                (
                    new_id(),
                    qid,
                    "base_rate",
                    body.base_rate,
                    body.base_rate_note or "tasa base declarada",
                    now_iso(),
                ),
            )
    return {"id": qid}


@router.get("/forecasts/calibration")
def calibration(forecaster: str = "user") -> dict[str, Any]:
    d = db()
    rows = d.all(
        """SELECT f.probability, q.outcome FROM forecast f JOIN forecast_question q ON q.id = f.question_id
           WHERE q.status = 'resolved' AND f.forecaster = ? AND f.id IN (SELECT id FROM forecast f2 WHERE f2.question_id = f.question_id AND f2.forecaster = f.forecaster ORDER BY made_at DESC LIMIT 1)""",
        (forecaster,),
    )
    pairs = []
    for r in rows:
        o = loads(r["outcome"], {}) or {}
        if "value" in o:
            pairs.append((float(r["probability"]), int(o["value"])))
    cal = fmath.calibration(pairs)
    forecasters = [
        r["forecaster"] for r in d.all("SELECT DISTINCT forecaster FROM forecast_score ORDER BY forecaster")
    ]
    summary = [
        dict(r)
        for r in d.all(
            "SELECT forecaster, COUNT(*) n, AVG(brier) brier, AVG(log_score) log_score FROM forecast_score GROUP BY forecaster ORDER BY brier"
        )
    ]
    base = next((s for s in summary if s["forecaster"] == "base_rate"), None)
    for s in summary:
        s["bss_vs_base_rate"] = (
            fmath.brier_skill_score(s["brier"], base["brier"]) if base and base["brier"] else None
        )
    return {"forecaster": forecaster, "calibration": cal, "forecasters": forecasters, "summary": summary}


@router.get("/forecasts/{qid}")
def get_question(qid: str) -> dict[str, Any]:
    d = db()
    r = d.one("SELECT * FROM forecast_question WHERE id = ?", (qid,))
    if not r:
        raise HTTPException(404, "pregunta no encontrada")
    q = _question_out(d, r)
    if q["origin_event_id"]:
        ev = d.one("SELECT * FROM event WHERE id = ?", (q["origin_event_id"],))
        q["origin_event"] = event_out(ev) if ev else None
    return q


class ForecastIn(BaseModel):
    probability: float = Field(ge=0.0, le=1.0)
    rationale: str | None = None
    forecaster: str = "user"


@router.post("/forecasts/{qid}/forecast")
def add_forecast(qid: str, body: ForecastIn) -> dict[str, Any]:
    d = db()
    q = d.one("SELECT status FROM forecast_question WHERE id = ?", (qid,))
    if not q:
        raise HTTPException(404, "pregunta no encontrada")
    if q["status"] != "open":
        raise HTTPException(400, "la pregunta no está abierta")
    if body.forecaster not in ("user",):
        raise HTTPException(400, "desde la UI solo se registran pronósticos del usuario")
    with d.tx() as conn:
        conn.execute(
            "INSERT INTO forecast(id, question_id, forecaster, probability, rationale, made_at) VALUES (?,?,?,?,?,?)",
            (new_id(), qid, body.forecaster, body.probability, body.rationale, now_iso()),
        )
    # protocolo: el sistema solo se revela después de registrar el del usuario
    system = d.one(
        "SELECT probability FROM forecast WHERE question_id = ? AND forecaster IN ('atlas_final','base_rate') ORDER BY forecaster = 'atlas_final' DESC, made_at DESC LIMIT 1",
        (qid,),
    )
    return {"ok": True, "system_probability": system["probability"] if system else None}


class ResolveIn(BaseModel):
    outcome: int = Field(ge=0, le=1)
    note: str | None = None


@router.post("/forecasts/{qid}/resolve")
def resolve_question(qid: str, body: ResolveIn) -> dict[str, Any]:
    d = db()
    q = d.one("SELECT * FROM forecast_question WHERE id = ?", (qid,))
    if not q:
        raise HTTPException(404, "pregunta no encontrada")
    scores = {}
    with d.tx() as conn:
        conn.execute(
            "UPDATE forecast_question SET status = 'resolved', resolved_at = ?, outcome = ? WHERE id = ?",
            (now_iso(), dumps({"value": body.outcome, "note": body.note}), qid),
        )
        # último pronóstico de cada pronosticador antes del cierre
        rows = conn.execute(
            "SELECT forecaster, probability FROM forecast WHERE question_id = ? ORDER BY made_at", (qid,)
        ).fetchall()
        last: dict[str, float] = {}
        for r in rows:
            last[r["forecaster"]] = r["probability"]
        for f, p in last.items():
            b = fmath.brier(p, body.outcome)
            ls = fmath.log_score(p, body.outcome)
            conn.execute(
                "INSERT OR REPLACE INTO forecast_score(question_id, forecaster, brier, log_score) VALUES (?,?,?,?)",
                (qid, f, round(b, 4), round(ls, 4)),
            )
            scores[f] = {"brier": round(b, 4), "log_score": round(ls, 4), "p": p}
    return {"ok": True, "scores": scores}


class LinkMarketIn(BaseModel):
    market_id: str


@router.post("/forecasts/{qid}/link_market")
def link_market(qid: str, body: LinkMarketIn) -> dict[str, Any]:
    d = db()
    m = d.one("SELECT * FROM prediction_market WHERE id = ?", (body.market_id,))
    if not m:
        raise HTTPException(404, "mercado no encontrado")
    with d.tx() as conn:
        conn.execute(
            "UPDATE forecast_question SET market_links = ? WHERE id = ?",
            (dumps([{"id": m["id"], "venue": m["venue"], "url": m["url"]}]), qid),
        )
        conn.execute(
            "INSERT INTO forecast(id, question_id, forecaster, probability, rationale, made_at) VALUES (?,?,?,?,?,?)",
            (new_id(), qid, f"market:{m['venue']}", m["probability"], m["question"], now_iso()),
        )
        conn.execute("UPDATE prediction_market SET followed = 1 WHERE id = ?", (m["id"],))
    return {"ok": True}


# ───────────── TALLER ─────────────

_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


class NoteIn(BaseModel):
    title: str | None = None
    body_text: str = ""
    course: str | None = None


def _note_out(d, r) -> dict[str, Any]:
    n = dict(r)
    n["links"] = loads(n["links"], [])
    return n


@router.get("/notes")
def list_notes(q: str | None = None) -> dict[str, Any]:
    d = db()
    if q:
        rows = d.all(
            "SELECT * FROM note WHERE title LIKE ? OR body_text LIKE ? ORDER BY updated_at DESC",
            (f"%{q}%", f"%{q}%"),
        )
    else:
        rows = d.all("SELECT * FROM note ORDER BY updated_at DESC LIMIT 200")
    return {"notes": [_note_out(d, r) for r in rows]}


@router.post("/notes")
def create_note(body: NoteIn) -> dict[str, Any]:
    d = db()
    nid = new_id()
    links = sorted(set(_LINK_RE.findall(body.body_text)))
    ts = now_iso()
    with d.tx() as conn:
        conn.execute(
            "INSERT INTO note(id, title, body_text, links, course, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (
                nid,
                body.title or (body.body_text[:60] or "Sin título"),
                body.body_text,
                dumps(links),
                body.course,
                ts,
                ts,
            ),
        )
    return {"id": nid}


@router.get("/notes/{note_id}")
def get_note(note_id: str) -> dict[str, Any]:
    d = db()
    r = d.one("SELECT * FROM note WHERE id = ?", (note_id,))
    if not r:
        raise HTTPException(404, "nota no encontrada")
    n = _note_out(d, r)
    back = [
        _note_out(d, x)
        for x in d.all("SELECT * FROM note WHERE id != ? AND links LIKE ?", (note_id, f'%"{n["title"]}"%'))
    ]
    n["backlinks"] = back
    marks = ",".join("?" for _ in n["links"])
    n["linked_entities"] = (
        [dict(x) for x in d.all(f"SELECT id, kind, name FROM entity WHERE name IN ({marks})", n["links"])]
        if n["links"]
        else []
    )
    return n


@router.put("/notes/{note_id}")
def update_note(note_id: str, body: NoteIn) -> dict[str, Any]:
    d = db()
    links = sorted(set(_LINK_RE.findall(body.body_text)))
    d.update(
        "note",
        note_id,
        {
            "title": body.title,
            "body_text": body.body_text,
            "links": dumps(links),
            "course": body.course,
            "updated_at": now_iso(),
        },
    )
    return {"ok": True}


@router.delete("/notes/{note_id}")
def delete_note(note_id: str) -> dict[str, Any]:
    d = db()
    with d.tx() as conn:
        conn.execute("DELETE FROM note WHERE id = ?", (note_id,))
    return {"ok": True}


@router.get("/notes/{note_id}/export.md", response_class=PlainTextResponse)
def export_note(note_id: str) -> str:
    d = db()
    r = d.one("SELECT * FROM note WHERE id = ?", (note_id,))
    if not r:
        raise HTTPException(404, "nota no encontrada")
    return f"# {r['title']}\n\n{r['body_text']}\n\n---\nDr. José Francisco Tornero-Aguilera · {r['updated_at'][:10]}\n"


class CardIn(BaseModel):
    front: str
    back: str
    source_ref: dict[str, Any] = Field(default_factory=dict)


@router.get("/cards")
def list_cards(due_only: bool = False) -> dict[str, Any]:
    d = db()
    sql = (
        "SELECT * FROM review_card"
        + (" WHERE due_at <= ?" if due_only else "")
        + " ORDER BY due_at LIMIT 200"
    )
    rows = d.all(sql, (now_iso(),) if due_only else ())
    out = []
    for r in rows:
        c = dict(r)
        c["fsrs_state"] = loads(c["fsrs_state"], {})
        c["source_ref"] = loads(c["source_ref"], {})
        out.append(c)
    return {
        "cards": out,
        "due": d.scalar("SELECT COUNT(*) FROM review_card WHERE due_at <= ?", (now_iso(),), 0),
    }


@router.post("/cards")
def create_card(body: CardIn) -> dict[str, Any]:
    d = db()
    cid = new_id()
    with d.tx() as conn:
        conn.execute(
            "INSERT INTO review_card(id, front, back, source_ref, fsrs_state, due_at, created_at) VALUES (?,?,?,?,?,?,?)",
            (
                cid,
                body.front,
                body.back,
                dumps(body.source_ref),
                dumps({"interval": 0, "ease": 2.5, "reps": 0, "lapses": 0}),
                now_iso(),
                now_iso(),
            ),
        )
    return {"id": cid}


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=4)  # 1 otra vez · 2 difícil · 3 bien · 4 fácil


def schedule(state: dict[str, Any], rating: int) -> dict[str, Any]:
    """FSRS-lite (planificador tipo SM-2 con estabilidad creciente). Devuelve el nuevo estado con `interval` en días."""
    interval = float(state.get("interval", 0) or 0)
    ease = float(state.get("ease", 2.5) or 2.5)
    reps = int(state.get("reps", 0) or 0)
    lapses = int(state.get("lapses", 0) or 0)
    if rating == 1:
        interval, ease, lapses = 0.0, max(1.3, ease - 0.2), lapses + 1
        reps = 0
    else:
        if reps == 0:
            interval = {2: 1.0, 3: 2.0, 4: 4.0}[rating]
        elif reps == 1:
            interval = {2: 3.0, 3: 6.0, 4: 10.0}[rating]
        else:
            factor = {2: 1.2, 3: ease, 4: ease * 1.3}[rating]
            interval = max(interval + 1, round(interval * factor, 1))
        ease = max(1.3, ease + {2: -0.15, 3: 0.0, 4: 0.15}[rating])
        reps += 1
    return {"interval": interval, "ease": round(ease, 2), "reps": reps, "lapses": lapses}


@router.post("/cards/{card_id}/review")
def review_card(card_id: str, body: ReviewIn) -> dict[str, Any]:
    d = db()
    r = d.one("SELECT fsrs_state FROM review_card WHERE id = ?", (card_id,))
    if not r:
        raise HTTPException(404, "tarjeta no encontrada")
    st = schedule(loads(r["fsrs_state"], {}), body.rating)
    due = datetime.now(UTC) + timedelta(
        days=st["interval"] if st["interval"] > 0 else 0, minutes=10 if st["interval"] == 0 else 0
    )
    d.update(
        "review_card", card_id, {"fsrs_state": dumps(st), "due_at": due.replace(microsecond=0).isoformat()}
    )
    return {"ok": True, "state": st, "due_at": due.isoformat()}


@router.delete("/cards/{card_id}")
def delete_card(card_id: str) -> dict[str, Any]:
    d = db()
    with d.tx() as conn:
        conn.execute("DELETE FROM review_card WHERE id = ?", (card_id,))
    return {"ok": True}
