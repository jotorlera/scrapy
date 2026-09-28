"""Materialidad (0-100) con desglose transparente (docs/spec/07 §2).

M = 100·σ(β0 + Σ βᵢ·fᵢ − β_v·virality_only). Los pesos viven en config/materiality.yaml. El desglose se guarda en
`event.materiality_breakdown` y se muestra en la UI. La relevancia para el usuario está acotada a +10 puntos.
"""

from __future__ import annotations

import math
import re
from typing import Any

from ..config_loader import attention_level, materiality_config, profile_config
from ..db import Database, dumps, loads
from ..embed import normalize_text
from ..util import parse_iso

POWER_BY_COUNTRY = {
    "US": 1.0,
    "CN": 1.0,
    "RU": 0.85,
    "IN": 0.75,
    "DE": 0.75,
    "JP": 0.75,
    "GB": 0.75,
    "FR": 0.75,
    "BR": 0.6,
    "IT": 0.6,
    "SA": 0.6,
    "TR": 0.55,
    "IR": 0.55,
    "IL": 0.55,
    "KR": 0.55,
    "ES": 0.55,
    "MX": 0.5,
    "ID": 0.5,
    "UA": 0.5,
    "CA": 0.5,
    "AU": 0.45,
    "AR": 0.4,
    "EG": 0.4,
    "PK": 0.4,
    "NG": 0.4,
    "ZA": 0.4,
    "PL": 0.4,
    "NL": 0.4,
    "TW": 0.45,
    "KP": 0.4,
    "AE": 0.4,
    "QA": 0.35,
}
POWER_BY_INSTITUTION = {
    "institution:Unión Europea": 0.85,
    "institution:Naciones Unidas": 0.7,
    "institution:OTAN": 0.8,
    "institution:Reserva Federal": 0.85,
    "institution:Banco Central Europeo": 0.8,
    "institution:Fondo Monetario Internacional": 0.6,
    "institution:OPEP": 0.6,
    "institution:Corte Penal Internacional": 0.5,
    "institution:Organización Mundial de la Salud": 0.5,
    "institution:Comisión Europea": 0.8,
    "institution:Casa Blanca": 1.0,
    "institution:Kremlin": 0.85,
    "institution:Partido Comunista de China": 1.0,
    "institution:G7": 0.7,
    "institution:G20": 0.6,
    "institution:BRICS": 0.5,
}

_IRREVERSIBLE = [
    (
        0.9,
        r"\b(muere|fallece|murió|ha muerto|asesinad[oa]|dies|died|killed|assassinat|tué|gestorben|morto)\b",
    ),
    (0.9, r"\b(anexi[oó]n|annex|invade|invasi[oó]n|invasion|declara la guerra|declares war)\b"),
    (
        0.8,
        r"\b(aprueba|aprobad[oa]|promulga|entra en vigor|ratifica|ratified|signed into law|adopted|adopta|passes|enacted|verabschiedet|adopté)\b",
    ),
    (
        0.8,
        r"\b(sentencia firme|condena|condenado|sentenced|convicted|guilty|culpable|inhabilitad[oa]|acquitted|absuelto)\b",
    ),
    (
        0.8,
        r"\b(dimite|dimisión|renuncia|resigns|resignation|destituid[oa]|cesad[oa]|sacked|ousted|impeached|démission|zurückgetreten)\b",
    ),
    (0.7, r"\b(default|impago|quiebra|bankruptcy|rescate|bailout|nacionaliza|nationalis)\b"),
    (
        0.7,
        r"\b(elegid[oa]|gana las elecciones|wins election|elected|proclamad[oa]|investid[oa]|sworn in|jura el cargo)\b",
    ),
    (0.7, r"\b(alto el fuego|ceasefire|tregua|truce|acuerdo de paz|peace deal|firma|firmado|signed|signs)\b"),
    (
        0.6,
        r"\b(sanciona|sanciones|sanctions|embargo|aranceles?|tariffs?|prohíbe|ban|bans|veta|vetoes|veto)\b",
    ),
    (
        0.5,
        r"\b(sube los tipos|baja los tipos|rate hike|rate cut|recorta|raises rates|cuts rates|subida de tipos|bajada de tipos)\b",
    ),
    (
        0.4,
        r"\b(disuelve|dissolves|convoca elecciones|calls election|referéndum|referendum|moción de censura|no-confidence)\b",
    ),
]
_IRREVERSIBLE_RX = [(w, re.compile(p, re.I)) for w, p in _IRREVERSIBLE]
_FUTURE_RX = re.compile(
    r"\b(podría|puede que|amenaza con|threatens to|could|may|might|plans to|planea|propone|proposes|estudia|considers|pide|urges|calls for|reclama|quiere|wants)\b",
    re.I,
)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def irreversibility_score(texts: list[str]) -> float:
    best = 0.0
    for t in texts:
        if not t:
            continue
        future = bool(_FUTURE_RX.search(t))
        for w, rx in _IRREVERSIBLE_RX:
            if rx.search(t):
                score = w * (0.4 if future else 1.0)
                best = max(best, score)
    return min(1.0, best)


def user_relevance(countries: list[str], texts: list[str]) -> tuple[float, list[str]]:
    prof = profile_config()
    reasons: list[str] = []
    score = 0.0
    if any(attention_level(c) == "A" for c in countries):
        score += 0.5
        reasons.append("país de nivel A")
    blob = normalize_text(" ".join(t for t in texts if t))
    kws: list[str] = []
    for biz in prof.get("negocios", []) or []:
        kws += [normalize_text(k) for k in (biz.get("palabras_clave") or [])]
        kws += [normalize_text(s) for s in (biz.get("sectores") or [])]
    for area in prof.get("investigacion", {}).get("areas", []) or []:
        kws.append(normalize_text(area))
    hits = sorted({k for k in kws if k and k in blob})
    if hits:
        score += min(0.5, 0.25 * len(hits))
        reasons.append("palabras clave del perfil: " + ", ".join(hits[:3]))
    concepts = prof.get("estudios", {}).get("conceptos_a_etiquetar", {}) or {}
    chits = []
    for _, lst in concepts.items():
        for c in lst or []:
            if normalize_text(c) in blob:
                chits.append(c)
    if chits:
        score += 0.2
        reasons.append("conceptos del grado: " + ", ".join(chits[:2]))
    return min(1.0, score), reasons


def compute_materiality(db: Database, event_id: str) -> dict[str, Any]:
    cfg = materiality_config()
    w = cfg.get("weights", {})
    beta0 = float(cfg.get("beta0", -2.0))
    ev = db.one("SELECT * FROM event WHERE id = ?", (event_id,))
    if ev is None:
        return {}
    docs = db.all(
        """SELECT d.id, d.title, d.lede, d.published_at, d.source_id, s.tier, s.region_bloc, s.type AS stype, s.ideology_label
           FROM document d JOIN source s ON s.id = d.source_id WHERE d.event_id = ? ORDER BY d.published_at""",
        (event_id,),
    )
    countries = loads(ev["countries"], [])
    keys = loads(ev["entity_keys"], [])
    texts = [f"{d['title']}. {d['lede'] or ''}" for d in docs[:30]]

    n_delta = db.scalar("SELECT COUNT(*) FROM state_delta WHERE event_id = ?", (event_id,), 0) or 0
    f_delta = min(1.0, n_delta / 2.0)

    power_vals = [POWER_BY_COUNTRY.get(c, 0.25) for c in countries] + [
        POWER_BY_INSTITUTION.get(k, 0.0) for k in keys
    ]
    f_power = max(power_vals) if power_vals else 0.15

    f_irrev = irreversibility_score(texts)

    blocs = {d["region_bloc"] for d in docs if d["region_bloc"]}
    f_breadth = min(1.0, max(0, len(countries) - 1) / 4.0 + (0.25 if len(blocs) >= 3 else 0.0))

    f_primary = 1.0 if any((d["tier"] or 4) == 1 for d in docs) else 0.0

    first = parse_iso(ev["first_seen_at"])
    last = parse_iso(ev["last_update_at"])
    age_h = ((last - first).total_seconds() / 3600.0) if (first and last) else 0.0
    f_novelty = 1.0 if age_h < 24 else max(0.0, 1.0 - (age_h - 24) / 144.0)

    f_user, user_reasons = user_relevance(countries, texts)

    all_sources = {d["source_id"] for d in docs}
    indep_sources = {d["source_id"] for d in docs if (d["tier"] or 4) <= 2}
    # cobertura independiente: cuenta a partir de la segunda fuente; más si cruza bloques
    n_ind = max(0, len(indep_sources) - 1)
    f_cov = min(1.0, math.log1p(n_ind) / math.log(8)) * (1.0 if len(blocs) >= 2 else 0.6)
    single_source = len(all_sources) <= 1
    # un solo emisor (aunque sea primario) no acredita por sí solo poder ni irreversibilidad: se atenúan
    damp = 0.5 if single_source else 1.0

    n_docs = len(docs)
    virality = 1.0 if (n_docs >= 15 and f_delta == 0 and f_primary == 0 and f_irrev < 0.4) else 0.0

    contrib = {
        "delta_state": float(w.get("delta_state", 1.4)) * f_delta,
        "power": float(w.get("power", 0.9)) * f_power * damp,
        "irreversibility": float(w.get("irreversibility", 1.1)) * f_irrev * damp,
        "breadth": float(w.get("breadth", 0.6)) * f_breadth,
        "primary_document": float(w.get("primary_document", 0.5)) * f_primary,
        "novelty": float(w.get("novelty", 0.4)) * f_novelty * (0.5 if single_source else 1.0),
        "independent_coverage": float(w.get("independent_coverage", 0.6)) * f_cov,
        "virality_only_penalty": -float(w.get("virality_only_penalty", 0.8)) * virality,
    }
    base = beta0 + sum(contrib.values())
    m_without_user = 100.0 * _sigmoid(base)
    m_with_user = 100.0 * _sigmoid(base + float(w.get("user_relevance", 0.5)) * f_user)
    user_bonus = min(10.0, m_with_user - m_without_user)
    m = round(min(100.0, m_without_user + user_bonus), 1)

    breakdown = {
        "score": m,
        "beta0": beta0,
        "features": {
            "delta_state": round(f_delta, 3),
            "power": round(f_power, 3),
            "irreversibility": round(f_irrev, 3),
            "breadth": round(f_breadth, 3),
            "primary_document": f_primary,
            "novelty": round(f_novelty, 3),
            "independent_coverage": round(f_cov, 3),
            "user_relevance": round(f_user, 3),
            "virality_only": virality,
        },
        "contributions": {k: round(v, 3) for k, v in contrib.items()},
        "user_bonus_points": round(user_bonus, 2),
        "user_reasons": user_reasons,
        "n_docs": n_docs,
        "n_sources": len(all_sources),
        "single_source": single_source,
        "n_independent_sources": len(indep_sources),
        "blocs": sorted(blocs),
        "method": "logistic (config/materiality.yaml)",
    }
    with db.tx() as conn:
        conn.execute(
            "UPDATE event SET materiality = ?, materiality_breakdown = ? WHERE id = ?",
            (m, dumps(breakdown), event_id),
        )
    return breakdown
