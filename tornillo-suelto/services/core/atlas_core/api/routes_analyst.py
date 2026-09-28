"""Modo ANALISTA: RADAR, EVENTOS, PRISMA, PRIMARIAS (+DIFF), MERCADOS, PAÍSES, ACTORES."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..config_loader import attention_level, causal_channels_config, countries_config
from ..db import loads
from ..engines.archive import analogs, compare_cases
from ..engines.claims import claims_for_event
from ..engines.coverage import BLOC_ORDER, IDEOLOGY_ORDER
from ..engines.diff import diff_documents
from ..engines.lexicon import fightin_words
from ..engines.state import recent_deltas
from ..gazetteer import countries as gazetteer_countries
from .deps import db, doc_out, event_out

router = APIRouter()

PRIMARY_TYPES = ("institution", "central_bank", "court", "statistical_office", "intl_org")


@router.get("/radar")
def radar(
    hours: int = Query(24, ge=1, le=720),
    domain: str | None = None,
    country: str | None = None,
    min_materiality: float = 0,
    limit: int = 60,
) -> dict[str, Any]:
    d = db()
    sql = "SELECT * FROM event WHERE status != 'merged' AND last_update_at >= datetime('now', ?) AND materiality >= ?"
    params: list[Any] = [f"-{hours} hours", min_materiality]
    if domain:
        sql += " AND domain = ?"
        params.append(domain)
    if country:
        sql += " AND countries LIKE ?"
        params.append(f'%"{country}"%')
    sql += " ORDER BY materiality DESC, n_docs DESC LIMIT ?"
    params.append(limit)
    events = [event_out(r) for r in d.all(sql, params)]
    deltas = recent_deltas(d, hours=max(hours, 72))
    counts = {
        "events": d.scalar(
            "SELECT COUNT(*) FROM event WHERE status != 'merged' AND last_update_at >= datetime('now', ?)",
            (f"-{hours} hours",),
            0,
        ),
        "documents": d.scalar(
            "SELECT COUNT(*) FROM document WHERE fetched_at >= datetime('now', ?)", (f"-{hours} hours",), 0
        ),
        "sources_ok": d.scalar(
            "SELECT COUNT(*) FROM source WHERE last_ok_at >= datetime('now', '-1 day')", (), 0
        ),
    }
    by_domain = {
        r["domain"]: r["n"]
        for r in d.all(
            "SELECT domain, COUNT(*) n FROM event WHERE status != 'merged' AND last_update_at >= datetime('now', ?) GROUP BY domain",
            (f"-{hours} hours",),
        )
    }
    return {"events": events, "deltas": deltas, "counts": counts, "by_domain": by_domain, "hours": hours}


@router.get("/events")
def list_events(
    hours: int = 168,
    limit: int = 100,
    q: str | None = None,
    country: str | None = None,
    domain: str | None = None,
    offset: int = 0,
) -> dict[str, Any]:
    d = db()
    sql = "SELECT * FROM event WHERE status != 'merged' AND last_update_at >= datetime('now', ?)"
    params: list[Any] = [f"-{hours} hours"]
    if q:
        sql += " AND title_neutral LIKE ?"
        params.append(f"%{q}%")
    if country:
        sql += " AND countries LIKE ?"
        params.append(f'%"{country}"%')
    if domain:
        sql += " AND domain = ?"
        params.append(domain)
    sql += " ORDER BY materiality DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    return {"events": [event_out(r) for r in d.all(sql, params)]}


@router.get("/events/{event_id}")
def event_detail(event_id: str) -> dict[str, Any]:
    d = db()
    row = d.one("SELECT * FROM event WHERE id = ?", (event_id,))
    if not row:
        raise HTTPException(404, "evento no encontrado")
    ev = event_out(row)
    docs = [
        doc_out(r)
        for r in d.all(
            """SELECT d.*, s.name AS source_name, s.slug AS source_slug, s.tier, s.type AS source_type, s.ideology_label, s.region_bloc,
                      s.state_relation, s.country AS source_country, s.paywall
               FROM document d JOIN source s ON s.id = d.source_id WHERE d.event_id = ? ORDER BY d.published_at ASC""",
            (event_id,),
        )
    ]
    claims = claims_for_event(d, event_id)
    revisions = []
    for c in claims:
        for r in c["revisions"]:
            revisions.append({**r, "claim_text": c["text_canonical"]})
    timeline = sorted(
        [
            {
                "t": x["published_at"],
                "kind": "document",
                "title": x["title"],
                "source": x["source_name"],
                "tier": x["tier"],
                "url": x["url"],
                "id": x["id"],
            }
            for x in docs
        ]
        + [
            {
                "t": r["changed_at"],
                "kind": "revision",
                "title": f"{r['old_status']} → {r['new_status']}: {r['claim_text'][:120]}",
                "source": "sistema",
                "tier": None,
                "url": None,
                "id": r["claim_id"],
            }
            for r in revisions
        ],
        key=lambda x: x["t"] or "",
    )
    deltas = [
        dict(r)
        for r in d.all(
            "SELECT sd.*, sv.scope, sv.dimension, sv.key FROM state_delta sd JOIN state_variable sv ON sv.id = sd.variable_id WHERE sd.event_id = ?",
            (event_id,),
        )
    ]
    keys = ev.get("entity_keys") or []
    related = []
    if keys:
        cand = d.all(
            "SELECT * FROM event WHERE id != ? AND status != 'merged' AND last_update_at >= datetime('now', '-30 days') ORDER BY last_update_at DESC LIMIT 400",
            (event_id,),
        )
        for c in cand:
            ck = set(loads(c["entity_keys"], []))
            inter = len(ck & set(keys))
            if inter >= 1 and (inter >= 2 or len(keys) <= 2):
                e = event_out(c)
                e["shared_entities"] = inter
                related.append(e)
        related.sort(key=lambda e: (-e["shared_entities"], -(e["materiality"] or 0)))
        related = related[:8]
    questions = [
        dict(r)
        for r in d.all(
            "SELECT * FROM forecast_question WHERE origin_event_id = ? ORDER BY open_at DESC", (event_id,)
        )
    ]
    for q in questions:
        q["countries"] = loads(q["countries"], [])
        q["market_links"] = loads(q["market_links"], [])
        q["latest"] = {
            r["forecaster"]: r["probability"]
            for r in d.all(
                "SELECT forecaster, probability FROM forecast WHERE question_id = ? ORDER BY made_at",
                (q["id"],),
            )
        }
    exposures = [
        dict(r)
        for r in d.all(
            "SELECT ea.*, b.name AS business_name FROM exposure_alert ea JOIN business_unit b ON b.id = ea.business_id WHERE ea.event_id = ? AND ea.dismissed = 0",
            (event_id,),
        )
    ]
    entities = [
        dict(r)
        for r in d.all(
            """SELECT e.id, e.kind, e.name, e.country, SUM(de.salience) AS salience, COUNT(*) AS n
           FROM document_entity de JOIN entity e ON e.id = de.entity_id JOIN document doc ON doc.id = de.document_id
           WHERE doc.event_id = ? GROUP BY e.id ORDER BY salience DESC LIMIT 15""",
            (event_id,),
        )
    ]
    agent_runs = [
        dict(r)
        for r in d.all(
            "SELECT id, kind, status, created_at, finished_at, cost_usd FROM agent_run WHERE ref = ? ORDER BY created_at DESC LIMIT 20",
            (event_id,),
        )
    ]
    an = analogs(d, f"{ev['title_neutral']}. {ev.get('domain')}", top_n=3)
    markets = [
        dict(r)
        for r in d.all(
            "SELECT * FROM prediction_market WHERE followed = 1 OR volume > 50000 ORDER BY volume DESC LIMIT 200"
        )
    ]
    pm_related = _related_markets(ev, markets)
    return {
        "event": ev,
        "documents": docs,
        "claims": claims,
        "timeline": timeline,
        "deltas": deltas,
        "related": related,
        "questions": questions,
        "exposures": exposures,
        "entities": entities,
        "agent_runs": agent_runs,
        "analogs": {"cases": an, "compare": compare_cases(an) if an else None},
        "prediction_markets": pm_related,
    }


def _related_markets(ev: dict[str, Any], markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from ..embed import tokens

    ev_tokens = set(tokens(ev["title_neutral"])) | {
        k.split(":", 1)[1].lower() for k in ev.get("entity_keys") or []
    }
    cmap = gazetteer_countries()
    for c in ev.get("countries") or []:
        if c in cmap:
            ev_tokens |= set(tokens(cmap[c].name_en)) | set(tokens(cmap[c].name_es))
    out = []
    for m in markets:
        mt = set(tokens(m["question"]))
        inter = len(mt & ev_tokens)
        if inter >= 2:
            out.append({**m, "overlap": inter})
    out.sort(key=lambda m: (-m["overlap"], -(m["volume"] or 0)))
    return out[:5]


class FlagIn(BaseModel):
    flag: str


@router.post("/events/{event_id}/flag")
def flag_event(event_id: str, body: FlagIn) -> dict[str, Any]:
    if body.flag not in ("important", "noise", ""):
        raise HTTPException(400, "flag debe ser important|noise|''")
    d = db()
    with d.tx() as conn:
        conn.execute("UPDATE event SET user_flag = ? WHERE id = ?", (body.flag or None, event_id))
    return {"ok": True}


@router.get("/events/{event_id}/prism")
def prism(event_id: str) -> dict[str, Any]:
    d = db()
    row = d.one("SELECT * FROM event WHERE id = ?", (event_id,))
    if not row:
        raise HTTPException(404, "evento no encontrado")
    ev = event_out(row)
    docs = [
        dict(r)
        for r in d.all(
            """SELECT d.id, d.title, d.lede, d.lang, d.published_at, d.url, s.name AS source_name, s.ideology_label, s.region_bloc, s.state_relation, s.type AS stype, s.tier, s.country
           FROM document d JOIN source s ON s.id = d.source_id WHERE d.event_id = ?""",
            (event_id,),
        )
    ]
    cov = ev.get("coverage_stats") or {}
    matrix = cov.get("matrix") or {}
    rows = [r for r in IDEOLOGY_ORDER if r in matrix] + [r for r in matrix if r not in IDEOLOGY_ORDER]
    cols = [c for c in BLOC_ORDER if any(c in matrix.get(r, {}) for r in rows)] + sorted(
        {c for r in rows for c in matrix.get(r, {}) if c not in BLOC_ORDER}
    )
    groups_ideo: dict[str, list[str]] = {}
    groups_bloc: dict[str, list[str]] = {}
    for x in docs:
        t = f"{x['title']} {x['lede'] or ''}"
        groups_ideo.setdefault(x["ideology_label"] or "unknown", []).append(t)
        groups_bloc.setdefault(x["region_bloc"] or "global", []).append(t)
    lexicon = {
        "ideology": fightin_words(groups_ideo) if len(groups_ideo) > 1 else {},
        "bloc": fightin_words(groups_bloc) if len(groups_bloc) > 1 else {},
    }
    state_media = [x for x in docs if x["state_relation"] in ("state_controlled", "state_aligned")]
    frames = [dict(r) for r in d.all("SELECT * FROM frame WHERE event_id = ?", (event_id,))]
    representative: dict[str, list[dict[str, Any]]] = {}
    for x in docs:
        k = x["ideology_label"] or "unknown"
        if len(representative.setdefault(k, [])) < 3:
            representative[k].append(
                {
                    "source": x["source_name"],
                    "title": x["title"],
                    "url": x["url"],
                    "lang": x["lang"],
                    "bloc": x["region_bloc"],
                }
            )
    return {
        "event": ev,
        "matrix": {"rows": rows, "cols": cols, "cells": matrix},
        "axes": cov.get("axes", {}),
        "silences": cov.get("silences", []),
        "lexicon": lexicon,
        "state_media": state_media,
        "frames": frames,
        "representative": representative,
        "n_docs": len(docs),
        "method": {
            "silence": "S_k=(E_k−O_k)/√E_k, E_k=V·s_k (cuota 30 días); silencio si S>2 y E≥5",
            "lexicon": "log-odds con prior de Dirichlet (Monroe et al., 2008)",
        },
    }


@router.get("/primaries")
def primaries(
    hours: int = 168,
    source_slug: str | None = None,
    country: str | None = None,
    kind: str | None = None,
    limit: int = 150,
) -> dict[str, Any]:
    d = db()
    sql = """SELECT d.*, s.name AS source_name, s.slug AS source_slug, s.type AS source_type, s.country AS source_country, s.tier
             FROM document d JOIN source s ON s.id = d.source_id WHERE s.tier = 1 AND d.fetched_at >= datetime('now', ?)"""
    params: list[Any] = [f"-{hours} hours"]
    if source_slug:
        sql += " AND s.slug = ?"
        params.append(source_slug)
    if country:
        sql += " AND s.country = ?"
        params.append(country)
    if kind:
        sql += " AND d.kind = ?"
        params.append(kind)
    sql += " ORDER BY d.published_at DESC LIMIT ?"
    params.append(limit)
    docs = [doc_out(r) for r in d.all(sql, params)]
    sources = [
        dict(r)
        for r in d.all(
            """SELECT s.slug, s.name, s.country, s.type, COUNT(d.id) AS n, MAX(d.published_at) AS last
           FROM source s LEFT JOIN document d ON d.source_id = s.id AND d.fetched_at >= datetime('now', '-30 days')
           WHERE s.tier = 1 AND s.active = 1 GROUP BY s.id ORDER BY n DESC"""
        )
    ]
    lineages = [
        dict(r)
        for r in d.all(
            """SELECT s.slug, s.name, COUNT(d.id) AS n FROM source s JOIN document d ON d.source_id = s.id
           WHERE s.tier = 1 AND s.type IN ('central_bank','institution','statistical_office') GROUP BY s.id HAVING n >= 2 ORDER BY n DESC"""
        )
    ]
    return {"documents": docs, "sources": sources, "lineages": lineages}


@router.get("/documents/{doc_id}")
def document(doc_id: str) -> dict[str, Any]:
    d = db()
    r = d.one(
        "SELECT d.*, s.name AS source_name, s.tier, s.type AS source_type, s.ideology_label, s.region_bloc FROM document d JOIN source s ON s.id = d.source_id WHERE d.id = ?",
        (doc_id,),
    )
    if not r:
        raise HTTPException(404, "documento no encontrado")
    out = dict(r)
    out.pop("embedding", None)
    for f in ("authors", "countries", "meta"):
        out[f] = loads(out[f], [] if f != "meta" else {})
    out["claims"] = [
        dict(c)
        for c in d.all(
            "SELECT c.*, ce.quote FROM claim c JOIN claim_evidence ce ON ce.claim_id = c.id AND ce.document_id = c.document_id WHERE c.document_id = ?",
            (doc_id,),
        )
    ]
    return out


@router.get("/diff")
def diff(old: str, new: str) -> dict[str, Any]:
    d = db()
    a = d.one("SELECT id, title, text, lede, published_at, url FROM document WHERE id = ?", (old,))
    b = d.one("SELECT id, title, text, lede, published_at, url FROM document WHERE id = ?", (new,))
    if not a or not b:
        raise HTTPException(404, "documento no encontrado")
    res = diff_documents(a["text"] or a["lede"] or "", b["text"] or b["lede"] or "")
    res["old"] = dict(a) | {"text": None}
    res["new"] = dict(b) | {"text": None}
    return res


@router.get("/markets")
def markets() -> dict[str, Any]:
    d = db()
    quotes = [dict(r) for r in d.all("SELECT * FROM market_quote ORDER BY group_name, label")]
    for q in quotes:
        q["history"] = loads(q["history"], [])
    pm = [
        dict(r) for r in d.all("SELECT * FROM prediction_market ORDER BY followed DESC, volume DESC LIMIT 60")
    ]
    for m in pm:
        m["tags"] = loads(m["tags"], [])
    channels = causal_channels_config().get("channels", [])
    last = d.one("SELECT finished_at, ok, stats FROM job_run WHERE job = 'markets' ORDER BY id DESC LIMIT 1")
    return {
        "quotes": quotes,
        "prediction_markets": pm,
        "channels": channels,
        "last_refresh": dict(last) if last else None,
        "disclaimer": "Información, no asesoramiento financiero. ATLAS nunca emite órdenes de compra o venta.",
    }


@router.post("/markets/prediction/{market_id:path}/follow")
def follow_market(market_id: str, follow: bool = True) -> dict[str, Any]:
    d = db()
    with d.tx() as conn:
        conn.execute(
            "UPDATE prediction_market SET followed = ? WHERE id = ?", (1 if follow else 0, market_id)
        )
    return {"ok": True}


@router.get("/countries")
def list_countries() -> dict[str, Any]:
    d = db()
    cfg = countries_config()
    out = []
    counts = {}
    for r in d.all(
        "SELECT countries FROM event WHERE status != 'merged' AND last_update_at >= datetime('now', '-7 days')"
    ):
        for c in loads(r["countries"], []):
            counts[c] = counts.get(c, 0) + 1
    for c in gazetteer_countries().values():
        out.append(
            {
                "iso2": c.iso2,
                "name": c.name_es,
                "name_en": c.name_en,
                "lat": c.lat,
                "lon": c.lon,
                "bloc": c.bloc,
                "level": attention_level(c.iso2),
                "events_7d": counts.get(c.iso2, 0),
            }
        )
    out.sort(key=lambda x: (x["level"], -x["events_7d"], x["name"]))
    return {"countries": out, "blocs": cfg.get("bloques_supranacionales", [])}


@router.get("/countries/{iso2}")
def country_sheet(iso2: str, days: int = 7) -> dict[str, Any]:
    d = db()
    iso2 = iso2.upper()
    c = gazetteer_countries().get(iso2)
    if not c:
        raise HTTPException(404, "país no encontrado en el gazetteer")
    events = [
        event_out(r)
        for r in d.all(
            "SELECT * FROM event WHERE countries LIKE ? AND status != 'merged' AND last_update_at >= datetime('now', ?) ORDER BY materiality DESC LIMIT 40",
            (f'%"{iso2}"%', f"-{days} days"),
        )
    ]
    deltas = [
        dict(r)
        for r in d.all(
            """SELECT sd.*, sv.dimension, sv.key, sv.unit, e.title_neutral AS event_title FROM state_delta sd JOIN state_variable sv ON sv.id = sd.variable_id
           LEFT JOIN event e ON e.id = sd.event_id WHERE sv.scope = ? ORDER BY sd.detected_at DESC LIMIT 30""",
            (iso2,),
        )
    ]
    variables = [
        dict(r)
        for r in d.all(
            "SELECT sv.*, (SELECT value_num FROM state_observation o WHERE o.variable_id = sv.id ORDER BY observed_at DESC LIMIT 1) AS last_value, (SELECT observed_at FROM state_observation o WHERE o.variable_id = sv.id ORDER BY observed_at DESC LIMIT 1) AS last_at FROM state_variable sv WHERE sv.scope = ?",
            (iso2,),
        )
    ]
    for v in variables:
        v["threshold"] = loads(v["threshold"], {})
    # miniPRISMA: prensa nacional frente a extranjera sobre los eventos del país
    ids = [e["id"] for e in events]
    local = foreign = 0
    by_bloc: dict[str, int] = {}
    if ids:
        marks = ",".join("?" for _ in ids)
        for r in d.all(
            f"SELECT s.country, s.region_bloc, COUNT(*) n FROM document d JOIN source s ON s.id = d.source_id WHERE d.event_id IN ({marks}) GROUP BY s.country, s.region_bloc",
            ids,
        ):
            if r["country"] == iso2:
                local += r["n"]
            else:
                foreign += r["n"]
            by_bloc[r["region_bloc"] or "global"] = by_bloc.get(r["region_bloc"] or "global", 0) + r["n"]
    questions = [
        dict(r)
        for r in d.all(
            "SELECT * FROM forecast_question WHERE countries LIKE ? AND status = 'open' ORDER BY close_at",
            (f'%"{iso2}"%',),
        )
    ]
    for q in questions:
        q["countries"] = loads(q["countries"], [])
        q["market_links"] = loads(q["market_links"], [])
    changed = [
        e
        for e in events
        if (e.get("materiality") or 0) >= 40
        or ((e.get("materiality_breakdown") or {}).get("features", {}).get("irreversibility", 0) >= 0.6)
    ][:10]
    return {
        "country": {
            "iso2": iso2,
            "name": c.name_es,
            "name_en": c.name_en,
            "lat": c.lat,
            "lon": c.lon,
            "bloc": c.bloc,
            "level": attention_level(iso2),
        },
        "events": events,
        "deltas": deltas,
        "variables": variables,
        "coverage": {"local": local, "foreign": foreign, "by_bloc": by_bloc},
        "questions": questions,
        "what_changed": changed,
        "days": days,
    }


@router.get("/actors")
def actors(q: str | None = None, kind: str | None = None, limit: int = 60) -> dict[str, Any]:
    d = db()
    sql = """SELECT e.id, e.kind, e.name, e.country, e.wikidata_qid, e.attributes,
                    (SELECT COUNT(*) FROM document_entity de JOIN document doc ON doc.id = de.document_id WHERE de.entity_id = e.id AND doc.fetched_at >= datetime('now','-7 days')) AS mentions_7d
             FROM entity e WHERE 1=1"""
    params: list[Any] = []
    if q:
        sql += " AND (e.name LIKE ? OR e.aliases LIKE ?)"
        params += [f"%{q}%", f"%{q.lower()}%"]
    if kind:
        sql += " AND e.kind = ?"
        params.append(kind)
    sql += " ORDER BY mentions_7d DESC, e.name LIMIT ?"
    params.append(limit)
    rows = []
    for r in d.all(sql, params):
        x = dict(r)
        x["attributes"] = loads(x["attributes"], {})
        rows.append(x)
    return {"actors": rows}


@router.get("/actors/{entity_id}")
def actor(entity_id: str, days: int = 30) -> dict[str, Any]:
    d = db()
    e = d.one("SELECT * FROM entity WHERE id = ?", (entity_id,))
    if not e:
        raise HTTPException(404, "entidad no encontrada")
    ent = dict(e)
    ent["aliases"] = loads(ent["aliases"], [])
    ent["attributes"] = loads(ent["attributes"], {})
    docs = [
        doc_out(r)
        for r in d.all(
            """SELECT d.*, s.name AS source_name, s.tier, s.ideology_label, s.region_bloc, de.salience FROM document_entity de JOIN document d ON d.id = de.document_id
           JOIN source s ON s.id = d.source_id WHERE de.entity_id = ? AND d.fetched_at >= datetime('now', ?) ORDER BY d.published_at DESC LIMIT 80""",
            (entity_id, f"-{days} days"),
        )
    ]
    events = [
        event_out(r)
        for r in d.all(
            """SELECT e.* FROM event e WHERE e.id IN (SELECT DISTINCT d.event_id FROM document_entity de JOIN document d ON d.id = de.document_id WHERE de.entity_id = ? AND d.event_id IS NOT NULL)
           AND e.status != 'merged' ORDER BY e.materiality DESC LIMIT 20""",
            (entity_id,),
        )
    ]
    quotes = [
        dict(r)
        for r in d.all(
            """SELECT c.id, c.text_canonical, c.level, c.status, c.attributed_to, c.first_seen_at, d.url, s.name AS source_name FROM claim c JOIN document d ON d.id = c.document_id JOIN source s ON s.id = d.source_id
           WHERE c.attributed_to IS NOT NULL AND (c.attributed_to LIKE ? OR ? LIKE '%' || c.attributed_to || '%') ORDER BY c.first_seen_at DESC LIMIT 40""",
            (f"%{ent['name']}%", ent["name"]),
        )
    ]
    co = [
        dict(r)
        for r in d.all(
            """SELECT e2.id, e2.name, e2.kind, COUNT(*) n FROM document_entity a JOIN document_entity b ON a.document_id = b.document_id AND a.entity_id != b.entity_id
           JOIN entity e2 ON e2.id = b.entity_id JOIN document d ON d.id = a.document_id WHERE a.entity_id = ? AND d.fetched_at >= datetime('now', ?) GROUP BY e2.id ORDER BY n DESC LIMIT 15""",
            (entity_id, f"-{days} days"),
        )
    ]
    return {
        "entity": ent,
        "documents": docs,
        "events": events,
        "attributed_claims": quotes,
        "co_mentions": co,
    }
