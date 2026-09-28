"""BRIEF diario compuesto por reglas (composed_by='rules'); el editor LLM lo redacta cuando hay clave.

Cuotas (docs/spec/02 T2): MUNDO 5, ESPAÑA 5, EUROPA 5, EE. UU. 3, ORIENTE MEDIO 3, ECONOMÍA 5, GEOPOLÍTICA 5,
IDEAS 2, CIENCIA/IA/SALUD 3. Cada ítem: hechos con cita, divergencia narrativa, primaria, por qué importa y
concepto del grado. Cierra con una pregunta de pronóstico y una cuestión socrática.
"""

from __future__ import annotations

import random
from datetime import timedelta
from typing import Any

from ..config_loader import profile_config
from ..db import Database, dumps, loads, new_id, now_iso
from ..embed import normalize_text
from ..util import parse_iso
from .claims import claims_for_event

EU = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "SE", "GB", "CH", "NO", "UA", "RS", "MD", "AD", "MC"}
MIDEAST = {"IL", "PS", "IR", "SA", "AE", "QA", "SY", "LB", "IQ", "JO", "YE", "EG", "TR", "KW", "OM", "BH"}

SECTIONS = [
    ("ESPAÑA", 5), ("EUROPA", 5), ("EE. UU.", 3), ("ORIENTE MEDIO", 3), ("ECONOMÍA", 5), ("GEOPOLÍTICA", 5),
    ("CIENCIA / IA / SALUD", 3), ("IDEAS", 2), ("MUNDO", 5),
]

CONCEPT_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("trilema de Mundell", ("tipo de cambio", "exchange rate", "capital controls", "banco central", "divisa")),
    ("curva de Phillips", ("inflación", "inflation", "desempleo", "unemployment", "salarios", "wages")),
    ("dominancia fiscal", ("deuda", "debt", "déficit", "deficit", "tipos", "rates", "banco central")),
    ("ventaja comparativa", ("aranceles", "tariff", "comercio", "trade", "exportaciones", "exports")),
    ("riesgo moral", ("rescate", "bailout", "garantía", "guarantee", "banco", "bank")),
    ("externalidades", ("emisiones", "emissions", "contaminación", "pollution", "clima", "climate")),
    ("dilema de seguridad", ("rearme", "defensa", "defence", "defense", "misiles", "missiles", "otan", "nato")),
    ("equilibrio de poder", ("alianza", "alliance", "cumbre", "summit", "brics", "g7", "hegemon")),
    ("disuasión", ("nuclear", "deterrence", "misil", "missile", "ejército", "military")),
    ("interdependencia compleja", ("cadena de suministro", "supply chain", "sanciones", "sanctions", "chips", "energía", "energy")),
    ("guerra justa", ("civiles", "civilians", "bombardeo", "strike", "alto el fuego", "ceasefire", "rehenes", "hostages")),
    ("soberanía", ("frontera", "border", "migración", "migration", "secesión", "independencia", "independence", "referéndum")),
    ("legitimidad", ("elecciones", "election", "protesta", "protest", "golpe", "coup", "tribunal", "court")),
    ("separación de poderes", ("tribunal", "court", "juez", "judge", "supremo", "constitucional", "fiscal", "amnistía")),
    ("populismo", ("populis", "extrema derecha", "far-right", "far right", "ultraderecha", "antisistema")),
    ("polarización", ("polariza", "polarization", "crispación", "bloqueo", "gridlock")),
    ("estado de derecho", ("estado de derecho", "rule of law", "corrupción", "corruption", "independencia judicial")),
    ("paternalismo", ("prohibición", "ban", "regulación", "regulation", "salud pública", "public health", "vacuna", "vaccine")),
    ("justicia distributiva", ("impuestos", "taxes", "desigualdad", "inequality", "renta", "income", "pensiones", "pensions", "vivienda", "housing")),
    ("libertad negativa", ("censura", "censorship", "libertad de expresión", "free speech", "vigilancia", "surveillance")),
    ("geografía y poder", ("estrecho", "strait", "canal", "ártico", "arctic", "groenlandia", "greenland", "ormuz", "hormuz", "taiwán", "taiwan")),
]

SOCRATIC = [
    "¿Qué evidencia te haría cambiar de opinión sobre el titular que más te ha llamado la atención hoy?",
    "Elige un evento del brief: ¿qué diría de él un realista (Morgenthau) y qué un liberal institucionalista (Keohane)? ¿En qué hecho concreto discreparían?",
    "¿La noticia más repetida de hoy ha cambiado alguna variable de estado del mundo, o solo el volumen de cobertura?",
    "¿Cuál de las afirmaciones que has leído hoy es una opinión presentada como hecho? ¿Cómo lo has sabido?",
    "Si tuvieras que apostar: ¿qué probabilidad das a que el evento principal de hoy siga en portada dentro de 30 días? ¿Por qué?",
    "¿Qué ecosistema informativo NO ha cubierto el evento principal? ¿Qué explica mejor ese silencio: agenda, afinidad o restricciones?",
    "Toma la decisión política más comentada hoy: ¿es legítima por su origen (procedimiento) o por su resultado? ¿Cuál de los dos criterios pesa más para ti y por qué?",
    "¿Hay alguna analogía histórica invocada hoy por la prensa («como en 1938», «como en 2008»)? ¿Qué variables coinciden y cuáles no?",
]


def _section_for(ev: dict[str, Any]) -> str:
    cs = set(ev.get("countries") or [])
    dom = ev.get("domain") or ""
    if "ES" in cs or "AD" in cs or "MC" in cs:
        return "ESPAÑA"
    if dom == "health" or dom == "technology":
        return "CIENCIA / IA / SALUD"
    if dom == "economy":
        return "ECONOMÍA"
    if cs & MIDEAST and dom in ("conflict", "politics"):
        return "ORIENTE MEDIO"
    if "US" in cs and not (cs - {"US"}):
        return "EE. UU."
    if dom == "conflict":
        return "GEOPOLÍTICA"
    if cs & EU:
        return "EUROPA"
    if dom == "society" or dom == "law":
        return "IDEAS" if any(k in normalize_text(ev.get("title_neutral", "")) for k in ("filosof", "univers", "libro", "book", "idea", "debate")) else "MUNDO"
    return "MUNDO"


def concept_for(text: str) -> str | None:
    blob = normalize_text(text)
    prof_concepts = set()
    for lst in (profile_config().get("estudios", {}).get("conceptos_a_etiquetar", {}) or {}).values():
        prof_concepts |= {c for c in (lst or [])}
    for concept, kws in CONCEPT_RULES:
        if any(normalize_text(k) in blob for k in kws):
            return concept
    return None


def _why_it_matters(ev: dict[str, Any]) -> str:
    br = ev.get("materiality_breakdown") or {}
    contrib = br.get("contributions") or {}
    names = {
        "power": "actores de gran peso", "irreversibility": "cambio difícil de revertir", "breadth": "afecta a varios países",
        "primary_document": "hay documento primario", "independent_coverage": "cobertura independiente amplia",
        "delta_state": "mueve variables de estado", "novelty": "es nuevo",
    }
    top = sorted(((v, k) for k, v in contrib.items() if v > 0), reverse=True)[:2]
    reasons = [names.get(k, k) for _, k in top]
    if br.get("user_reasons"):
        reasons.append(br["user_reasons"][0])
    return "; ".join(reasons).capitalize() if reasons else "Materialidad baja: se incluye por cuota de sección."


def _divergence(ev: dict[str, Any]) -> str:
    cov = ev.get("coverage_stats") or {}
    sil = cov.get("silences") or []
    ideo = (cov.get("axes") or {}).get("ideology") or {}
    n_eco = len([k for k, v in ideo.items() if v.get("observed")])
    parts = [f"{cov.get('n_sources', 0)} fuentes, {n_eco} ecosistemas ideológicos, {len(cov.get('langs') or [])} idiomas."]
    if sil:
        s = sil[0]
        parts.append(f"Silencio en {s['ecosystem']} ({s['axis']}): esperadas {s['expected']}, observadas {s['observed']}.")
    return " ".join(parts)


def compose_brief(db: Database, kind: str = "study", hours: int = 24) -> dict[str, Any]:
    since = (parse_iso(now_iso()) - timedelta(hours=hours)).isoformat()  # type: ignore[operator]
    rows = db.all(
        """SELECT * FROM event WHERE status != 'merged' AND last_update_at >= ? ORDER BY materiality DESC LIMIT 300""",
        (since,),
    )
    events = []
    for r in rows:
        d = dict(r)
        for f in ("countries", "materiality_breakdown", "coverage_stats", "silence_index"):
            d[f] = loads(d.get(f), [] if f == "countries" else {})
        d.pop("centroid", None)
        events.append(d)
    quotas = dict(SECTIONS)
    if kind == "executive":
        quotas = {"ECONOMÍA": 5, "EUROPA": 4, "ESPAÑA": 4, "MUNDO": 4, "CIENCIA / IA / SALUD": 3}
    buckets: dict[str, list[dict[str, Any]]] = {s: [] for s in quotas}
    used: set[str] = set()
    for ev in events:
        sec = _section_for(ev)
        if sec not in buckets:
            sec = "MUNDO" if "MUNDO" in buckets else next(iter(buckets))
        if len(buckets[sec]) < quotas[sec] and ev["id"] not in used:
            buckets[sec].append(ev)
            used.add(ev["id"])
    # rellenar MUNDO con lo que sobre
    if "MUNDO" in buckets:
        for ev in events:
            if len(buckets["MUNDO"]) >= quotas["MUNDO"]:
                break
            if ev["id"] not in used:
                buckets["MUNDO"].append(ev)
                used.add(ev["id"])
    sections = []
    for name, _q in (SECTIONS if kind != "executive" else [(k, v) for k, v in quotas.items()]):
        items = []
        for ev in buckets.get(name, []):
            claims = claims_for_event(db, ev["id"], limit=8)
            facts = []
            for c in claims:
                if c["level"] == "opinion":
                    continue
                facts.append({"text": c["text_canonical"], "status": c["status"], "level": c["level"], "claim_id": c["id"], "document_id": c["document_id"], "source": c["source_name"], "url": c["doc_url"]})
                if len(facts) >= 3:
                    break
            primary = db.one(
                """SELECT d.title, d.url, s.name FROM document d JOIN source s ON s.id = d.source_id
                   WHERE d.event_id = ? AND s.tier = 1 ORDER BY d.published_at LIMIT 1""",
                (ev["id"],),
            )
            exposures = [dict(x) for x in db.all(
                "SELECT ea.channel, ea.confidence, b.name FROM exposure_alert ea JOIN business_unit b ON b.id = ea.business_id WHERE ea.event_id = ? AND ea.dismissed = 0",
                (ev["id"],),
            )]
            items.append(
                {
                    "event_id": ev["id"],
                    "title": ev["title_neutral"],
                    "materiality": ev["materiality"],
                    "countries": ev["countries"],
                    "domain": ev["domain"],
                    "facts": facts,
                    "narrative_divergence": _divergence(ev),
                    "primary_source": dict(primary) if primary else None,
                    "why_it_matters": _why_it_matters(ev),
                    "course_concept": concept_for(" ".join([ev["title_neutral"]] + [f["text"] for f in facts])),
                    "exposures": exposures,
                }
            )
        if items:
            sections.append({"name": name, "items": items})
    q = db.one("SELECT id, title, close_at FROM forecast_question WHERE status = 'open' ORDER BY RANDOM() LIMIT 1")
    content = {
        "date": now_iso()[:10],
        "kind": kind,
        "window_hours": hours,
        "sections": sections,
        "n_events_considered": len(events),
        "forecast_prompt": dict(q) if q else None,
        "socratic_prompt": random.choice(SOCRATIC),
        "reading_time_min": max(3, sum(len(s["items"]) for s in sections) * 0.4),
    }
    bid = new_id()
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO brief(id, date, kind, composed_by, content, created_at) VALUES (?,?,?,?,?,?)",
            (bid, content["date"], kind, "rules", dumps(content), now_iso()),
        )
    content["id"] = bid
    content["composed_by"] = "rules"
    return content
