"""Vocabulario diferencial por ecosistema: log-odds ratio con prior informativo de Dirichlet
(Monroe, Colaresi y Quinn, 2008, "Fightin' Words"). Determinista.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from ..embed import tokens


def fightin_words(
    groups: dict[str, list[str]], alpha0: float = 50.0, min_count: int = 2, top_n: int = 12
) -> dict[str, list[dict[str, Any]]]:
    """groups: {ecosistema: [textos]} → {ecosistema: [{term, z, count}]} con los términos que más lo distinguen."""
    counts: dict[str, Counter] = {g: Counter() for g in groups}
    for g, texts in groups.items():
        for t in texts:
            counts[g].update(w for w in tokens(t) if len(w) > 2 and not w.isdigit())
    total = Counter()
    for c in counts.values():
        total.update(c)
    n_total = sum(total.values())
    if n_total == 0:
        return {g: [] for g in groups}
    out: dict[str, list[dict[str, Any]]] = {}
    for g, c in counts.items():
        n_g = sum(c.values())
        rest = total - c
        n_r = sum(rest.values())
        if n_g == 0 or n_r == 0:
            out[g] = []
            continue
        scored = []
        for w, y_gw in c.items():
            if y_gw < min_count:
                continue
            a_w = alpha0 * total[w] / n_total
            y_rw = rest.get(w, 0)
            num_g = (y_gw + a_w) / (n_g + alpha0 - y_gw - a_w)
            num_r = (y_rw + a_w) / (n_r + alpha0 - y_rw - a_w)
            if num_g <= 0 or num_r <= 0:
                continue
            delta = math.log(num_g) - math.log(num_r)
            var = 1.0 / (y_gw + a_w) + 1.0 / (y_rw + a_w)
            z = delta / math.sqrt(var)
            scored.append({"term": w, "z": round(z, 2), "count": y_gw})
        scored.sort(key=lambda d: -d["z"])
        out[g] = [s for s in scored[:top_n] if s["z"] > 1.0]
    return out
