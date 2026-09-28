"""DIETA: diversidad de la dieta informativa (docs/spec/07 §8). Entropía de Shannon normalizada por eje sobre el
tiempo de lectura registrado localmente. Puntos ciegos: tema con ≥ X minutos y > 80% en un solo ecosistema.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import timedelta
from typing import Any

from ..db import Database, now_iso
from ..util import parse_iso

AXES = {"ideology": "ideology_label", "bloc": "region_bloc", "lang": "lang", "type": "type"}


def normalized_entropy(weights: dict[str, float]) -> float:
    total = sum(weights.values())
    k = len([w for w in weights.values() if w > 0])
    if total <= 0 or k <= 1:
        return 0.0
    h = -sum((w / total) * math.log(w / total) for w in weights.values() if w > 0)
    return h / math.log(k)


def diet_report(db: Database, days: int = 7, blind_spot_minutes: float = 5.0) -> dict[str, Any]:
    since = (parse_iso(now_iso()) - timedelta(days=days)).isoformat()  # type: ignore[operator]
    rows = db.all(
        """SELECT rl.action, rl.seconds, rl.topic, rl.event_id, d.lang, s.ideology_label, s.region_bloc, s.type, s.name
           FROM reading_log rl LEFT JOIN document d ON d.id = rl.document_id LEFT JOIN source s ON s.id = d.source_id
           WHERE rl.at >= ?""",
        (since,),
    )
    logs = [dict(r) for r in rows]
    axes: dict[str, dict[str, float]] = {a: defaultdict(float) for a in AXES}
    total_seconds = 0.0
    for r in logs:
        secs = float(r.get("seconds") or 0) or (30.0 if r.get("action") == "open" else 0.0)
        total_seconds += secs
        for axis, col in AXES.items():
            axes[axis][r.get(col) or "unknown"] += secs
    entropies = {a: round(normalized_entropy(dict(w)), 3) for a, w in axes.items()}
    diversity = round(sum(entropies.values()) / max(1, len(entropies)), 3)
    # puntos ciegos por tema: > 80% de los segundos en un solo ecosistema ideológico
    by_topic: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in logs:
        if not r.get("topic"):
            continue
        secs = float(r.get("seconds") or 0) or 30.0
        by_topic[r["topic"]][r.get("ideology_label") or "unknown"] += secs
    blind = []
    for topic, dist in by_topic.items():
        tot = sum(dist.values())
        if tot < blind_spot_minutes * 60:
            continue
        eco, secs = max(dist.items(), key=lambda kv: kv[1])
        share = secs / tot
        if share > 0.8:
            blind.append(
                {"topic": topic, "ecosystem": eco, "share": round(share, 2), "minutes": round(tot / 60, 1)}
            )
    return {
        "days": days,
        "minutes": round(total_seconds / 60, 1),
        "n_logs": len(logs),
        "entropy": entropies,
        "diversity_index": diversity,
        "distribution": {a: dict(sorted(w.items(), key=lambda kv: -kv[1])) for a, w in axes.items()},
        "blind_spots": blind,
    }
