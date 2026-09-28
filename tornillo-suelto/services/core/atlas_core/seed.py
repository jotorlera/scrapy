"""Carga de semillas: fuentes (fuentes.seed.yaml + feeds.yaml), entidades del gazetteer, negocios del perfil,
variables de estado, casos históricos, mapa argumental de la RBU. Idempotente."""

from __future__ import annotations

from typing import Any

from .config_loader import feeds_catalog, profile_config, sources_seed
from .db import Database, dumps, new_id, now_iso
from .engines.archive import embed_cases
from .engines.state import seed_state_variables
from .gazetteer import _INSTITUTIONS, countries
from .seed_data import HISTORICAL_CASES, RBU_MAP, SEED_NOTE

POLL_BY_TIER = {1: 20, 2: 20, 3: 45, 4: 90}
PRIMARY_TYPES = ("institution", "central_bank", "court", "statistical_office", "intl_org")


def _label(s: dict) -> str | None:
    """Etiqueta ideológica local; las fuentes primarias sin etiqueta son «institutional» por definición."""
    lab = s.get("lab")
    if not lab and s.get("t") in PRIMARY_TYPES:
        return "institutional"
    return lab


def seed_sources(db: Database) -> dict[str, int]:
    seeds = sources_seed()
    feeds = feeds_catalog()
    created = updated = 0
    ts = now_iso()
    with db.tx() as conn:
        for s in seeds:
            slug = s["slug"]
            row = conn.execute("SELECT id, feeds FROM source WHERE slug = ?", (slug,)).fetchone()
            feed_list = feeds.get(slug, [])
            if row is None:
                conn.execute(
                    """INSERT INTO source(id, slug, name, domain, type, tier, country, languages, region_bloc, state_relation,
                       ideology_label, paywall, feeds, feed_status, active, poll_minutes, review_status, group_name, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        new_id(),
                        slug,
                        s.get("name", slug),
                        s.get("domain"),
                        s.get("t", "newspaper"),
                        int(s.get("tier", 3)),
                        s.get("c"),
                        dumps(s.get("l") or []),
                        s.get("bloc"),
                        s.get("st"),
                        _label(s),
                        s.get("paywall", "none"),
                        dumps(feed_list),
                        "curated" if feed_list else "unknown",
                        1 if s.get("active", True) and s.get("t") != "data_api" else 0,
                        POLL_BY_TIER.get(int(s.get("tier", 3)), 45),
                        s.get("review_status", "seed_unverified"),
                        s.get("group"),
                        ts,
                    ),
                )
                created += 1
            else:
                # actualizar metadatos y feeds curados si la fuente aún no tiene feed
                conn.execute(
                    """UPDATE source SET name=?, domain=?, type=?, tier=?, country=?, languages=?, region_bloc=?, state_relation=?,
                       ideology_label=?, paywall=?, group_name=?,
                       feeds = CASE WHEN feeds = '[]' AND ? != '[]' THEN ? ELSE feeds END,
                       feed_status = CASE WHEN feeds = '[]' AND ? != '[]' THEN 'curated' ELSE feed_status END
                       WHERE id = ?""",
                    (
                        s.get("name", slug),
                        s.get("domain"),
                        s.get("t", "newspaper"),
                        int(s.get("tier", 3)),
                        s.get("c"),
                        dumps(s.get("l") or []),
                        s.get("bloc"),
                        s.get("st"),
                        _label(s),
                        s.get("paywall", "none"),
                        s.get("group"),
                        dumps(feed_list),
                        dumps(feed_list),
                        dumps(feed_list),
                        row["id"],
                    ),
                )
                updated += 1
    return {"created": created, "updated": updated}


def seed_entities(db: Database) -> int:
    n = 0
    ts = now_iso()
    with db.tx() as conn:
        for c in countries().values():
            key = f"country:{c.iso2}"
            if conn.execute(
                "SELECT 1 FROM entity WHERE json_extract(attributes, '$.key') = ?", (key,)
            ).fetchone():
                continue
            conn.execute(
                "INSERT INTO entity(id, kind, name, aliases, country, description, attributes, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    new_id(),
                    "country",
                    c.name_es,
                    dumps(list(c.aliases)),
                    c.iso2,
                    c.name_en,
                    dumps({"key": key, "lat": c.lat, "lon": c.lon, "bloc": c.bloc}),
                    ts,
                ),
            )
            n += 1
        for kind, name, aliases, country in _INSTITUTIONS:
            key = f"{kind}:{name}"
            if conn.execute(
                "SELECT 1 FROM entity WHERE json_extract(attributes, '$.key') = ?", (key,)
            ).fetchone():
                continue
            conn.execute(
                "INSERT INTO entity(id, kind, name, aliases, country, description, attributes, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (new_id(), kind, name, dumps(list(aliases)), country, None, dumps({"key": key}), ts),
            )
            n += 1
    return n


def seed_businesses(db: Database) -> int:
    prof = profile_config()
    n = 0
    with db.tx() as conn:
        for b in prof.get("negocios", []) or []:
            if conn.execute("SELECT 1 FROM business_unit WHERE name = ?", (b.get("nombre"),)).fetchone():
                continue
            conn.execute(
                "INSERT INTO business_unit(id, name, sectors, jurisdictions, markets, currencies, regulations, keywords) VALUES (?,?,?,?,?,?,?,?)",
                (
                    new_id(),
                    b.get("nombre"),
                    dumps(b.get("sectores") or []),
                    dumps(b.get("jurisdicciones") or []),
                    dumps([]),
                    dumps((prof.get("negocios_contexto") or {}).get("divisas_relevantes") or []),
                    dumps(b.get("regulacion_relevante") or []),
                    dumps(b.get("palabras_clave") or []),
                ),
            )
            n += 1
    return n


def seed_historical_cases(db: Database) -> int:
    n = 0
    with db.tx() as conn:
        for c in HISTORICAL_CASES:
            if conn.execute("SELECT 1 FROM historical_case WHERE name = ?", (c["name"],)).fetchone():
                continue
            conn.execute(
                """INSERT INTO historical_case(id, name, category, start_date, end_date, countries, variables, outcome, duration_months, summary, sources)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    new_id(),
                    c["name"],
                    c["category"],
                    c.get("start_date"),
                    c.get("end_date"),
                    dumps(c.get("countries") or []),
                    dumps(c.get("variables") or {}),
                    c.get("outcome"),
                    c.get("duration_months"),
                    c.get("summary"),
                    dumps([*c.get("sources", []), SEED_NOTE]),
                ),
            )
            n += 1
    embed_cases(db)
    return n


def seed_argument_map(db: Database) -> int:
    if db.one("SELECT 1 FROM argument_map WHERE title = ?", (RBU_MAP["title"],)):
        return 0
    ts = now_iso()
    map_id = new_id()
    ids: dict[str, str] = {}
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO argument_map(id, title, topic, created_at) VALUES (?,?,?,?)",
            (map_id, RBU_MAP["title"], RBU_MAP["topic"], ts),
        )
        for nd in RBU_MAP["nodes"]:
            nid = new_id()
            ids[nd["key"]] = nid
            conn.execute(
                "INSERT INTO argument_node(id, map_id, kind, text, author, work, is_user, x, y, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    nid,
                    map_id,
                    nd["kind"],
                    nd["text"],
                    nd.get("author"),
                    nd.get("work"),
                    1 if nd.get("is_user") else 0,
                    nd.get("x"),
                    nd.get("y"),
                    ts,
                ),
            )
        for src, dst, rel in RBU_MAP["edges"]:
            conn.execute(
                "INSERT INTO argument_edge(id, map_id, src, dst, rel) VALUES (?,?,?,?,?)",
                (new_id(), map_id, ids[src], ids[dst], rel),
            )
    return len(RBU_MAP["nodes"])


def seed_forecast_templates(db: Database) -> int:
    """Preguntas recurrentes (docs/spec/06 §2) con criterio de resolución explícito."""
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    q_end = (now.replace(day=1) + timedelta(days=95)).replace(day=1) - timedelta(days=1)
    templates = [
        (
            "¿Bajará el BCE el tipo de la facilidad de depósito en su próxima reunión de política monetaria?",
            "Resuelve SÍ si el comunicado de la próxima reunión del Consejo de Gobierno del BCE anuncia una reducción del tipo de la facilidad de depósito respecto del vigente. Fuente: ecb.europa.eu, comunicado de decisiones.",
            "BCE (comunicado oficial)",
            "economy",
            ["EU"],
            0.35,
            "Frecuencia histórica de recortes por reunión en ciclos de relajación (~40%).",
        ),
        (
            "¿Recortará la Reserva Federal el rango objetivo de los fondos federales en su próxima reunión del FOMC?",
            "Resuelve SÍ si el comunicado del FOMC anuncia un recorte del rango objetivo. Fuente: federalreserve.gov.",
            "Fed (comunicado del FOMC)",
            "economy",
            ["US"],
            0.35,
            "Frecuencia de recortes por reunión en ciclos de relajación.",
        ),
        (
            f"¿Cerrará el Brent por encima de 80 USD/barril el último día hábil del trimestre ({q_end.date()})?",
            f"Resuelve SÍ si el precio de cierre del futuro de Brent de primer vencimiento el {q_end.date()} es estrictamente superior a 80 USD. Fuente: ICE vía Yahoo Finance (BZ=F).",
            "ICE / Yahoo Finance BZ=F",
            "economy",
            ["world"],
            0.5,
            "Distribución histórica de variaciones trimestrales del Brent.",
        ),
        (
            "¿Estará en vigor un alto el fuego formal en Gaza al final del mes que viene?",
            "Resuelve SÍ si al último día del mes siguiente existe un alto el fuego anunciado por las partes o por un mediador (EE. UU., Egipto, Catar) y no ha sido declarado roto por ninguna de ellas. Fuente: comunicados oficiales y ONU.",
            "ONU / mediadores",
            "conflict",
            ["IL", "PS"],
            0.4,
            "Duración de altos el fuego previos (2014, 2021, 2023-24, 2025).",
        ),
        (
            "¿Superará la inflación interanual de la eurozona (IPCA flash) el 2,0% en el próximo dato mensual?",
            "Resuelve SÍ si el dato flash de Eurostat del IPCA interanual del mes siguiente es estrictamente superior al 2,0%. Fuente: Eurostat.",
            "Eurostat (IPCA flash)",
            "economy",
            ["EU"],
            0.5,
            "Frecuencia de lecturas por encima del objetivo en los últimos 24 meses.",
        ),
        (
            "¿Habrá elecciones generales anticipadas convocadas en España antes de fin de año?",
            "Resuelve SÍ si se publica en el BOE un real decreto de disolución de las Cortes y convocatoria de elecciones generales antes del 31 de diciembre. Fuente: BOE.",
            "BOE",
            "politics",
            ["ES"],
            0.15,
            "Tasa base de disoluciones anticipadas por año en legislaturas sin mayoría absoluta (1977-2025).",
        ),
    ]
    n = 0
    with db.tx() as conn:
        for title, criteria, source, domain, countries_, base_rate, note in templates:
            if conn.execute("SELECT 1 FROM forecast_question WHERE title = ?", (title,)).fetchone():
                continue
            conn.execute(
                """INSERT INTO forecast_question(id, title, resolution_criteria, resolution_source, kind, open_at, close_at, resolve_by,
                   domain, countries, base_rate, base_rate_note, market_links, status, created_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    new_id(),
                    title,
                    criteria,
                    source,
                    "binary",
                    now_iso(),
                    (now + timedelta(days=45)).replace(microsecond=0).isoformat(),
                    (now + timedelta(days=60)).replace(microsecond=0).isoformat(),
                    domain,
                    dumps(countries_),
                    base_rate,
                    note,
                    dumps([]),
                    "open",
                    "template",
                ),
            )
            n += 1
    return n


def seed_all(db: Database) -> dict[str, Any]:
    return {
        "sources": seed_sources(db),
        "entities": seed_entities(db),
        "businesses": seed_businesses(db),
        "state_variables": seed_state_variables(db),
        "historical_cases": seed_historical_cases(db),
        "argument_map_nodes": seed_argument_map(db),
        "forecast_templates": seed_forecast_templates(db),
    }
