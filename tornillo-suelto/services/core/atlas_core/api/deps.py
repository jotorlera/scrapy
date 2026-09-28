"""Dependencias y utilidades compartidas por los routers."""

from __future__ import annotations

from typing import Any

from ..db import Database, get_db, loads

EVENT_JSON = ("countries", "entity_keys", "materiality_breakdown", "coverage_stats", "silence_index", "geo")


def db() -> Database:
    return get_db()


def event_out(row) -> dict[str, Any]:
    d = dict(row)
    for f in EVENT_JSON:
        if f in d:
            d[f] = loads(d[f], [] if f in ("countries", "entity_keys") else None)
    d.pop("centroid", None)
    d.pop("embedding", None)
    cov = d.get("coverage_stats") or {}
    d["n_sources"] = cov.get("n_sources", 0)
    d["n_primary"] = cov.get("n_primary", 0)
    d["langs"] = cov.get("langs", [])
    d["silences"] = cov.get("silences", [])
    d["topics"] = cov.get("topics", [])
    ideo = (cov.get("axes") or {}).get("ideology") or {}
    d["ecosystems"] = {k: v.get("observed", 0) for k, v in ideo.items() if v.get("observed")}
    return d


def doc_out(row) -> dict[str, Any]:
    d = dict(row)
    d.pop("embedding", None)
    d.pop("text", None)
    for f in ("authors", "countries", "meta"):
        if f in d:
            d[f] = loads(d[f], [] if f != "meta" else {})
    return d
