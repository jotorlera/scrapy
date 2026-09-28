"""Cobertura por ecosistema e índice de silencio (docs/spec/07 §4).

E_k = V_e · s_k, con s_k la cuota de producción del ecosistema k en los últimos 30 días (documentos ingeridos).
S_k = (E_k − O_k) / sqrt(E_k)  (residuo de Poisson estandarizado). Se marca silencio si S_k > 2 y E_k ≥ 5.
Ecosistemas: por etiqueta ideológica local, por bloque regional, por idioma, por tipo y por relación con el Estado.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import timedelta
from typing import Any

from ..db import Database, dumps
from ..util import parse_iso

AXES = {
    "ideology": "ideology_label",
    "bloc": "region_bloc",
    "lang": "lang",
    "type": "type",
    "state": "state_relation",
}
IDEOLOGY_ORDER = [
    "left",
    "center_left",
    "center",
    "center_right",
    "right",
    "heterodox",
    "institutional",
    "unknown",
]
BLOC_ORDER = [
    "anglo",
    "eu",
    "es",
    "latam",
    "arab",
    "turkey",
    "russia",
    "china",
    "india",
    "japan_korea",
    "africa",
    "other_asia",
    "oceania",
    "global",
]


def _doc_attrs(db: Database, since_iso: str) -> list[dict[str, Any]]:
    rows = db.all(
        """SELECT d.event_id, d.lang, s.ideology_label, s.region_bloc, s.type, s.state_relation, s.tier
           FROM document d JOIN source s ON s.id = d.source_id WHERE d.fetched_at >= ?""",
        (since_iso,),
    )
    return [dict(r) for r in rows]


def baseline_shares(db: Database, days: int = 30) -> dict[str, dict[str, float]]:
    """Cuota de producción s_k por eje y ecosistema, últimos `days` días."""
    since = (parse_iso(db_now(db)) - timedelta(days=days)).isoformat()  # type: ignore[operator]
    docs = _doc_attrs(db, since)
    return shares_from_docs(docs)


def shares_from_docs(docs: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    n = max(1, len(docs))
    for axis, col in AXES.items():
        c = Counter((d.get(col) or "unknown") for d in docs)
        out[axis] = {k: v / n for k, v in c.items()}
    return out


def silence_index(
    observed: dict[str, int], shares: dict[str, float], total: int
) -> dict[str, dict[str, float]]:
    """Para un eje: {ecosistema: {expected, observed, s, silent}}."""
    out: dict[str, dict[str, float]] = {}
    keys = set(observed) | set(shares)
    for k in keys:
        e = total * shares.get(k, 0.0)
        o = observed.get(k, 0)
        s = (e - o) / math.sqrt(e) if e > 0 else 0.0
        out[k] = {
            "expected": round(e, 2),
            "observed": o,
            "s": round(s, 2),
            "silent": bool(s > 2.0 and e >= 5.0),
            "over": bool(s < -2.0 and o >= 5),
        }
    return out


def coverage_for_docs(docs: list[dict[str, Any]], shares: dict[str, dict[str, float]]) -> dict[str, Any]:
    total = len(docs)
    result: dict[str, Any] = {"n_docs": total, "axes": {}, "matrix": {}, "silences": []}
    for axis, col in AXES.items():
        obs = Counter((d.get(col) or "unknown") for d in docs)
        si = silence_index(dict(obs), shares.get(axis, {}), total)
        result["axes"][axis] = si
        for k, v in si.items():
            if v["silent"]:
                result["silences"].append({"axis": axis, "ecosystem": k, **v})
    # matriz ideología × bloque
    matrix: dict[str, dict[str, int]] = {}
    for d in docs:
        row = d.get("ideology_label") or "unknown"
        col = d.get("region_bloc") or "global"
        matrix.setdefault(row, {}).setdefault(col, 0)
        matrix[row][col] += 1
    result["matrix"] = matrix
    result["n_primary"] = sum(1 for d in docs if (d.get("tier") or 4) == 1)
    result["n_sources"] = len({d.get("source_id") for d in docs if d.get("source_id")})
    result["langs"] = sorted({d.get("lang") for d in docs if d.get("lang")})
    return result


def db_now(db: Database) -> str:
    from ..db import now_iso

    return now_iso()


def compute_coverage(
    db: Database, event_id: str, shares: dict[str, dict[str, float]] | None = None
) -> dict[str, Any]:
    if shares is None:
        shares = baseline_shares(db)
    rows = db.all(
        """SELECT d.source_id, d.lang, s.ideology_label, s.region_bloc, s.type, s.state_relation, s.tier
           FROM document d JOIN source s ON s.id = d.source_id WHERE d.event_id = ?""",
        (event_id,),
    )
    docs = [dict(r) for r in rows]
    cov = coverage_for_docs(docs, shares)
    prev = db.one("SELECT coverage_stats FROM event WHERE id = ?", (event_id,))
    prev_stats = {}
    if prev and prev["coverage_stats"]:
        from ..db import loads

        prev_stats = loads(prev["coverage_stats"], {}) or {}
    if "topics" in prev_stats:
        cov["topics"] = prev_stats["topics"]
    with db.tx() as conn:
        conn.execute(
            "UPDATE event SET coverage_stats = ?, silence_index = ? WHERE id = ?",
            (dumps(cov), dumps(cov["silences"]), event_id),
        )
    return cov
