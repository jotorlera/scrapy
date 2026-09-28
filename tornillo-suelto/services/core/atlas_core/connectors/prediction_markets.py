"""Mercados de predicción (solo lectura; ATLAS nunca opera). Polymarket Gamma API y Manifold API.

Metaculus devuelve 403 sin cabeceras de navegador: conector preparado y desactivado (ADR-0005).
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from ..db import Database, now_iso
from ..gazetteer import find_mentions

POLYMARKET_URL = "https://gamma-api.polymarket.com/markets"
MANIFOLD_URL = "https://api.manifold.markets/v0/search-markets"

MANIFOLD_TERMS = ("election", "ceasefire", "Fed rate", "ECB", "tariff", "recession", "Ukraine", "Iran", "Spain", "China Taiwan", "inflation", "NATO")

RELEVANT_HINTS = (
    "election", "elecciones", "president", "prime minister", "ceasefire", "war", "invasion", "nato", "tariff",
    "fed", "rate", "ecb", "inflation", "recession", "gdp", "sanction", "ukraine", "russia", "china", "taiwan",
    "iran", "israel", "gaza", "government", "parliament", "referendum", "eu ", "european", "spain", "france",
    "germany", "uk ", "brexit", "oil", "opec", "debt", "default", "impeach", "supreme court", "who ", "pandemic",
    "vaccine", "ai ", "openai", "regulation", "minister", "coup", "protest", "strike", "treaty", "summit",
)


def _relevant(question: str) -> bool:
    q = " " + question.lower() + " "
    if any(h in q for h in RELEVANT_HINTS):
        return True
    return bool([m for m in find_mentions(question) if m.kind in ("country", "institution")])


async def fetch_polymarket(client: httpx.AsyncClient, limit: int = 200) -> list[dict[str, Any]]:
    params = {"active": "true", "closed": "false", "limit": str(limit), "order": "volume24hr", "ascending": "false"}
    r = await client.get(POLYMARKET_URL, params=params)
    r.raise_for_status()
    out = []
    for m in r.json():
        q = m.get("question") or ""
        if not q:
            continue
        try:
            prices = m.get("outcomePrices")
            if isinstance(prices, str):
                prices = json.loads(prices)
            outcomes = m.get("outcomes")
            if isinstance(outcomes, str):
                outcomes = json.loads(outcomes)
            prob = None
            if prices and outcomes:
                for o, p in zip(outcomes, prices, strict=False):
                    if str(o).lower() == "yes":
                        prob = float(p)
                        break
                if prob is None:
                    prob = float(prices[0])
        except (ValueError, TypeError):
            prob = None
        if prob is None:
            continue
        out.append(
            {
                "id": f"polymarket:{m.get('id')}",
                "venue": "polymarket",
                "market_id": str(m.get("id")),
                "question": q,
                "probability": prob,
                "volume": float(m.get("volumeNum") or m.get("volume") or 0),
                "liquidity": float(m.get("liquidityNum") or m.get("liquidity") or 0),
                "url": f"https://polymarket.com/market/{m.get('slug')}" if m.get("slug") else "https://polymarket.com",
                "close_at": m.get("endDate"),
                "tags": [],
            }
        )
    return out


async def fetch_manifold(client: httpx.AsyncClient, per_term: int = 15) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for term in MANIFOLD_TERMS:
        try:
            r = await client.get(
                MANIFOLD_URL, params={"term": term, "sort": "liquidity", "filter": "open", "limit": str(per_term)}
            )
            r.raise_for_status()
        except httpx.HTTPError:
            continue
        for m in r.json():
            if m.get("outcomeType") != "BINARY" or m.get("probability") is None:
                continue
            mid = str(m.get("id"))
            out[mid] = {
                "id": f"manifold:{mid}",
                "venue": "manifold",
                "market_id": mid,
                "question": m.get("question", ""),
                "probability": float(m["probability"]),
                "volume": float(m.get("volume") or 0),
                "liquidity": float(m.get("totalLiquidity") or 0),
                "url": m.get("url") or "https://manifold.markets",
                "close_at": None,
                "tags": [term],
            }
    return list(out.values())


def store_markets(db: Database, markets: list[dict[str, Any]]) -> int:
    n = 0
    ts = now_iso()
    with db.tx() as conn:
        for m in markets:
            if not _relevant(m["question"]):
                continue
            close_at = m.get("close_at")
            if isinstance(close_at, (int, float)):
                close_at = None
            conn.execute(
                """INSERT INTO prediction_market(id, venue, market_id, question, probability, volume, liquidity, url,
                   close_at, fetched_at, tags)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET probability=excluded.probability, volume=excluded.volume,
                   liquidity=excluded.liquidity, fetched_at=excluded.fetched_at, close_at=excluded.close_at""",
                (
                    m["id"], m["venue"], m["market_id"], m["question"], m["probability"], m["volume"], m["liquidity"],
                    m["url"], close_at, ts, json.dumps(m.get("tags") or []),
                ),
            )
            n += 1
    return n


async def refresh_prediction_markets(db: Database, client: httpx.AsyncClient) -> dict[str, Any]:
    stats: dict[str, Any] = {"polymarket": 0, "manifold": 0, "errors": []}
    try:
        pm = await fetch_polymarket(client)
        stats["polymarket"] = store_markets(db, pm)
    except (httpx.HTTPError, ValueError) as e:
        stats["errors"].append(f"polymarket: {type(e).__name__}: {e}")
    try:
        mf = await fetch_manifold(client)
        stats["manifold"] = store_markets(db, mf)
    except (httpx.HTTPError, ValueError) as e:
        stats["errors"].append(f"manifold: {type(e).__name__}: {e}")
    return stats
