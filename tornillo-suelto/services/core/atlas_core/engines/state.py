"""Variables de estado y deltas (docs/spec/04 y 07 §6).

Dos fuentes reales de deltas en esta fase, ambas con procedencia:
1. MONEY.fx_vs_usd desde la cinta de mercados (Yahoo): variación semanal por encima del umbral → delta.
2. Cambios categóricos detectados en eventos con irreversibilidad alta (dimisión, ley adoptada, sentencia,
   alto el fuego…) → delta en POWER / RULES / FORCE / EXTERNAL enlazado al evento y al documento fuente.
"""

from __future__ import annotations

import re
from typing import Any

from ..config_loader import countries_config, profile_config
from ..db import Database, dumps, loads, new_id, now_iso

SEED_VARIABLES = [
    ("MONEY", "policy_rate", "%", {"type": "abs", "value": 0.25}, "Banco central (comunicado)"),
    ("MONEY", "cpi_yoy", "%", {"type": "abs", "value": 0.3}, "Oficina estadística"),
    ("MONEY", "fx_vs_usd", "%/7d", {"type": "abs", "value": 2.0}, "Yahoo Finance (cinta)"),
    ("MONEY", "10y_yield", "pb", {"type": "abs", "value": 25}, "Mercado"),
    ("POWER", "head_of_government", "categorical", {"type": "categorical"}, "Afirmación confirmada"),
    (
        "RULES",
        "major_law_adopted_30d",
        "count",
        {"type": "categorical"},
        "Boletín oficial / afirmación confirmada",
    ),
    ("RULES", "court_ruling_major_30d", "count", {"type": "categorical"}, "Tribunal / afirmación confirmada"),
    ("FORCE", "ceasefire_status", "categorical", {"type": "categorical"}, "Afirmación confirmada"),
    ("FORCE", "major_attack_30d", "count", {"type": "categorical"}, "Afirmación confirmada"),
    ("EXTERNAL", "sanctions_active_count", "count", {"type": "categorical"}, "Listas oficiales"),
    (
        "LEGITIMACY",
        "protest_events_30d",
        "count",
        {"type": "zscore", "window_days": 90, "value": 2.0},
        "ACLED (requiere clave)",
    ),
]

FX_SYMBOL_TO_COUNTRY = {
    "USDJPY=X": "JP",
    "USDCNY=X": "CN",
    "USDTRY=X": "TR",
    "USDBRL=X": "BR",
    "USDMXN=X": "MX",
    "EURUSD=X": "EU",
}

CATEGORICAL_RULES: list[tuple[str, str, str, re.Pattern]] = [
    (
        "POWER",
        "head_of_government",
        "cambio o crisis en la jefatura de Gobierno",
        re.compile(
            r"\b(dimite|dimisión|renuncia|resigns|resignation|destituid|ousted|impeach|jura el cargo|sworn in|investid|gana las elecciones|wins election|elected|démission|zurückgetreten)\b",
            re.I,
        ),
    ),
    (
        "RULES",
        "major_law_adopted_30d",
        "norma adoptada o en vigor",
        re.compile(
            r"\b(aprueba la ley|aprobada la ley|entra en vigor|promulga|ratifica|signed into law|adopted|passes law|enacted|verabschiedet|adopté)\b",
            re.I,
        ),
    ),
    (
        "RULES",
        "court_ruling_major_30d",
        "sentencia relevante",
        re.compile(
            r"\b(sentencia|condena|condenado|sentenced|convicted|ruling|falla|anula|strikes down|absuelto|acquitted)\b",
            re.I,
        ),
    ),
    (
        "FORCE",
        "ceasefire_status",
        "cambio en alto el fuego",
        re.compile(r"\b(alto el fuego|ceasefire|tregua|truce|cessez-le-feu|waffenruhe)\b", re.I),
    ),
    (
        "FORCE",
        "major_attack_30d",
        "ataque de gran escala",
        re.compile(
            r"\b(bombardeo|airstrike|misiles|missile strike|ofensiva|offensive|atentado|attack kills|killed at least|masacre|massacre)\b",
            re.I,
        ),
    ),
    (
        "EXTERNAL",
        "sanctions_active_count",
        "sanciones o aranceles",
        re.compile(r"\b(sanciona|sanciones|sanctions|aranceles|tariffs|embargo)\b", re.I),
    ),
    (
        "MONEY",
        "policy_rate",
        "decisión de tipos",
        re.compile(
            r"\b(sube los tipos|baja los tipos|rate hike|rate cut|raises rates|cuts rates|mantiene los tipos|holds rates|subida de tipos|bajada de tipos|recorta los tipos)\b",
            re.I,
        ),
    ),
]


def seed_state_variables(db: Database) -> int:
    cfg = countries_config()
    extra = profile_config().get("preferencias_atlas", {}).get("paises_nivel_A_extra", []) or []
    scopes = list(dict.fromkeys(list(cfg.get("A", [])) + list(extra) + ["EU", "world"]))
    n = 0
    with db.tx() as conn:
        for scope in scopes:
            for dim, key, unit, threshold, hint in SEED_VARIABLES:
                if scope == "world" and key not in ("fx_vs_usd", "major_attack_30d"):
                    continue
                cur = conn.execute(
                    "SELECT 1 FROM state_variable WHERE scope = ? AND key = ?", (scope, key)
                ).fetchone()
                if cur:
                    continue
                conn.execute(
                    "INSERT INTO state_variable(id, scope, dimension, key, unit, source_hint, threshold) VALUES (?,?,?,?,?,?,?)",
                    (new_id(), scope, dim, key, unit, hint, dumps(threshold)),
                )
                n += 1
    return n


def _variable_id(db: Database, scope: str, key: str, create: bool = False) -> str | None:
    r = db.one("SELECT id FROM state_variable WHERE scope = ? AND key = ?", (scope, key))
    if r:
        return r["id"]
    if not create:
        return None
    spec = next((v for v in SEED_VARIABLES if v[1] == key), None)
    if spec is None:
        return None
    dim, _key, unit, threshold, hint = spec
    vid = new_id()
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO state_variable(id, scope, dimension, key, unit, source_hint, threshold) VALUES (?,?,?,?,?,?,?)",
            (vid, scope, dim, key, unit, hint, dumps(threshold)),
        )
    return vid


def deltas_from_markets(db: Database) -> int:
    """MONEY.fx_vs_usd: variación en 5 sesiones (≈ 7 días naturales) desde el histórico de la cinta.

    La variable se crea si no existe (como hace deltas_from_event): todo símbolo de FX_SYMBOL_TO_COUNTRY registra
    observación aunque su país no sea de nivel A (JP), en vez de descartarse en silencio."""
    n = 0
    ts = now_iso()
    for sym, scope in FX_SYMBOL_TO_COUNTRY.items():
        q = db.one("SELECT history, observed_at, price FROM market_quote WHERE symbol = ?", (sym,))
        if not q or not q["history"]:
            continue
        hist = loads(q["history"], [])
        if len(hist) < 6:
            continue
        last = hist[-1]["v"]
        prev = hist[-6]["v"]
        if not prev:
            continue
        pct = (last - prev) / prev * 100.0
        vid = _variable_id(db, scope, "fx_vs_usd", create=True)
        if not vid:
            continue
        threshold = loads(
            db.one("SELECT threshold FROM state_variable WHERE id = ?", (vid,))["threshold"], {}
        )
        with db.tx() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO state_observation(variable_id, observed_at, value_num, source_note)
                   VALUES (?,?,?,?)""",
                (
                    vid,
                    q["observed_at"] or ts,
                    round(pct, 3),
                    f"Yahoo Finance {sym}: variación 5 sesiones (≈7 días)",
                ),
            )
            if abs(pct) >= float(threshold.get("value", 2.0)):
                exists = conn.execute(
                    "SELECT 1 FROM state_delta WHERE variable_id = ? AND detected_at >= date('now','-6 days')",
                    (vid,),
                ).fetchone()
                if not exists:
                    direction = (
                        "se deprecia"
                        if (pct > 0 and sym != "EURUSD=X") or (pct < 0 and sym == "EURUSD=X")
                        else "se aprecia"
                    )
                    conn.execute(
                        "INSERT INTO state_delta(id, variable_id, event_id, detected_at, magnitude, description) VALUES (?,?,?,?,?,?)",
                        (
                            new_id(),
                            vid,
                            None,
                            ts,
                            round(pct, 2),
                            f"{sym}: {pct:+.1f}% en 5 sesiones (≈7 días) ({direction} frente al USD). Fuente: Yahoo Finance",
                        ),
                    )
                    n += 1
    return n


def deltas_from_event(db: Database, event_id: str) -> int:
    ev = db.one(
        "SELECT id, title_neutral, countries, materiality_breakdown, lead_document_id FROM event WHERE id = ?",
        (event_id,),
    )
    if not ev:
        return 0
    br = loads(ev["materiality_breakdown"], {}) or {}
    feats = br.get("features", {})
    # Solo cambios acreditados: irreversibilidad alta, y o bien ≥ 2 fuentes o bien documento primario
    if (feats.get("irreversibility") or 0) < 0.7:
        return 0
    if br.get("single_source") and not feats.get("primary_document"):
        return 0
    countries = loads(ev["countries"], [])
    if not countries:
        return 0
    lead = db.one("SELECT title, lede, id FROM document WHERE id = ?", (ev["lead_document_id"],))
    if lead is None:
        lead = db.one(
            "SELECT title, lede, id FROM document WHERE event_id = ? ORDER BY published_at LIMIT 1",
            (event_id,),
        )
    if lead is None:
        return 0  # sin documento no hay procedencia (source_doc_id) que mostrar ni que distinguir en materialidad
    # la regla debe cumplirse en el TÍTULO (el cambio es el asunto, no un detalle de la entradilla)
    text = f"{ev['title_neutral']} {lead['title'] or ''}"
    n = 0
    ts = now_iso()
    matched = [(dim, key, label) for dim, key, label, rx in CATEGORICAL_RULES if rx.search(text)]
    if not matched:
        return 0
    scope = countries[0]
    var_ids = {key: _variable_id(db, scope, key, create=True) for _dim, key, _label in matched}
    with db.tx() as conn:
        for dim, key, label in matched:
            vid = var_ids.get(key)
            if not vid:
                continue
            if True:
                dup = conn.execute(
                    "SELECT 1 FROM state_delta WHERE variable_id = ? AND event_id = ?", (vid, event_id)
                ).fetchone()
                if dup:
                    continue
                conn.execute(
                    "INSERT INTO state_delta(id, variable_id, event_id, detected_at, magnitude, description, source_doc_id) VALUES (?,?,?,?,?,?,?)",
                    (
                        new_id(),
                        vid,
                        event_id,
                        ts,
                        1.0,
                        f"{scope} · {dim} · {label}: {ev['title_neutral'][:140]}",
                        lead["id"],
                    ),
                )
                n += 1
    return n


def recent_deltas(db: Database, hours: int = 168, limit: int = 40) -> list[dict[str, Any]]:
    rows = db.all(
        """SELECT sd.*, sv.scope, sv.dimension, sv.key, sv.unit, sv.source_hint, e.title_neutral AS event_title,
                  d.url AS source_url, d.title AS source_title
           FROM state_delta sd JOIN state_variable sv ON sv.id = sd.variable_id
           LEFT JOIN event e ON e.id = sd.event_id LEFT JOIN document d ON d.id = sd.source_doc_id
           WHERE sd.detected_at >= datetime('now', ?) ORDER BY sd.detected_at DESC LIMIT ?""",
        (f"-{hours} hours", limit),
    )
    return [dict(r) for r in rows]
