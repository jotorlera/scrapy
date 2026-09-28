"""Dependencias y utilidades compartidas por los routers."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Query

from ..db import Database, get_db, loads

EVENT_JSON = ("countries", "entity_keys", "materiality_breakdown", "coverage_stats", "silence_index", "geo")

# Cotas de paginación y ventanas temporales. Sin ellas `LIMIT -1` en SQLite significa "sin límite" y una sola
# petición serializa la tabla `event` entera (decenas de MB); un entero enorme daba 500 (OverflowError).
# Cada endpoint conserva su propio valor por defecto; los máximos cubren lo que usa apps/web.
LimitQ = Annotated[int, Query(ge=1, le=500)]  # UI máx: 300 (/events en Megatendencias)
OffsetQ = Annotated[int, Query(ge=0, le=100_000)]
HoursQ = Annotated[int, Query(ge=1, le=8760)]  # UI usa exactamente 24*365 en /primaries (linaje)
DaysQ = Annotated[int, Query(ge=1, le=365)]  # UI: 1/7/30 (países), 7/30/90 (dieta)
TopNQ = Annotated[int, Query(ge=1, le=20)]  # /archive/analogs


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
