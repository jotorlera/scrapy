"""Matemática del motor de pronóstico (docs/spec/06): agregación, mezcla con mercado, Brier, log score,
Brier Skill Score, calibración con intervalos de Wilson y descomposición de Murphy.
"""

from __future__ import annotations

import math
from typing import Any

EPS = 0.02


def clip(p: float, lo: float = EPS, hi: float = 1 - EPS) -> float:
    return max(lo, min(hi, p))


def logit(p: float) -> float:
    p = clip(p, 1e-6, 1 - 1e-6)
    return math.log(p / (1 - p))


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def aggregate_ensemble(
    probs: list[float], weights: list[float] | None = None, a: float = 1.5
) -> dict[str, float]:
    """Media ponderada de log-odds + extremización. Devuelve raw y extremized."""
    if not probs:
        raise ValueError("sin pronósticos")
    if weights is None:
        weights = [1.0] * len(probs)
    wsum = sum(weights)
    logit_agg = sum(w * logit(p) for p, w in zip(probs, weights, strict=True)) / wsum
    return {"raw": sigmoid(logit_agg), "extremized": sigmoid(a * logit_agg), "logit_agg": logit_agg, "a": a}


def blend_with_market(p_ens: float, market: float | None, alpha: float = 0.4) -> float:
    if market is None:
        return p_ens
    return sigmoid(alpha * logit(p_ens) + (1 - alpha) * logit(market))


def brier(p: float, outcome: int) -> float:
    return (p - outcome) ** 2


def log_score(p: float, outcome: int) -> float:
    p = clip(p, 0.01, 0.99)
    return math.log(p if outcome == 1 else 1 - p)


def brier_skill_score(brier_model: float, brier_ref: float) -> float | None:
    if brier_ref <= 0:
        return None
    return 1.0 - brier_model / brier_ref


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    phat = k / n
    denom = 1 + z * z / n
    centre = phat + z * z / (2 * n)
    adj = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return (max(0.0, (centre - adj) / denom), min(1.0, (centre + adj) / denom))


def calibration(pairs: list[tuple[float, int]], bins: int = 10) -> dict[str, Any]:
    """pairs: (probabilidad, resultado 0/1). Curva por deciles + Murphy (fiabilidad, resolución, incertidumbre)."""
    n = len(pairs)
    if n == 0:
        return {
            "n": 0,
            "bins": [],
            "brier": None,
            "reliability": None,
            "resolution": None,
            "uncertainty": None,
        }
    base = sum(o for _, o in pairs) / n
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for p, o in pairs:
        i = min(bins - 1, int(clip(p, 0, 1 - 1e-9) * bins))
        buckets[i].append((p, o))
    out_bins = []
    reliability = 0.0
    resolution = 0.0
    for i, b in enumerate(buckets):
        lo, hi = i / bins, (i + 1) / bins
        if not b:
            out_bins.append({"lo": lo, "hi": hi, "n": 0, "mean_p": None, "freq": None, "ci": None})
            continue
        k = sum(o for _, o in b)
        mean_p = sum(p for p, _ in b) / len(b)
        freq = k / len(b)
        ci = wilson(k, len(b))
        reliability += len(b) * (mean_p - freq) ** 2
        resolution += len(b) * (freq - base) ** 2
        out_bins.append(
            {
                "lo": lo,
                "hi": hi,
                "n": len(b),
                "mean_p": round(mean_p, 3),
                "freq": round(freq, 3),
                "ci": [round(ci[0], 3), round(ci[1], 3)],
            }
        )
    brier_mean = sum(brier(p, o) for p, o in pairs) / n
    return {
        "n": n,
        "bins": out_bins,
        "brier": round(brier_mean, 4),
        "reliability": round(reliability / n, 4),
        "resolution": round(resolution / n, 4),
        "uncertainty": round(base * (1 - base), 4),
        "base_rate": round(base, 3),
    }


def question_quality_issues(title: str, criteria: str, base_rate: float | None) -> list[str]:
    issues = []
    if len(title.strip()) < 15 or "?" not in title:
        issues.append("El título debe ser una pregunta cerrada (con '?').")
    if len(criteria.strip()) < 30:
        issues.append("El criterio de resolución debe nombrar fuente, umbral y definición (≥ 30 caracteres).")
    if base_rate is not None and not (0.03 <= base_rate <= 0.97):
        issues.append("Tasa base fuera de [3%, 97%]: pregunta trivial.")
    return issues
