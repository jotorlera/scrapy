"""Cinta de mercados: endpoint público de gráficos de Yahoo Finance (sin clave). ADR-0005.

Cada cotización guarda su hora de observación y su fuente. Si una serie falla, se conserva el último dato
válido y se anota el error: la UI muestra la fecha, nunca un dato inventado.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import httpx

from ..db import Database, now_iso
from ..util import to_iso


def _ts(ts: float | int) -> str | None:
    return to_iso(datetime.fromtimestamp(ts, tz=UTC))


CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# símbolo, etiqueta, grupo
SYMBOLS: list[tuple[str, str, str]] = [
    ("^GSPC", "S&P 500", "indices"),
    ("^STOXX50E", "Euro Stoxx 50", "indices"),
    ("^IBEX", "IBEX 35", "indices"),
    ("^N225", "Nikkei 225", "indices"),
    ("000001.SS", "Shanghái", "indices"),
    ("EURUSD=X", "EUR/USD", "fx"),
    ("USDJPY=X", "USD/JPY", "fx"),
    ("USDCNY=X", "USD/CNY", "fx"),
    ("USDTRY=X", "USD/TRY", "fx"),
    ("USDBRL=X", "USD/BRL", "fx"),
    ("USDMXN=X", "USD/MXN", "fx"),
    ("BZ=F", "Brent", "commodities"),
    ("CL=F", "WTI", "commodities"),
    ("NG=F", "Henry Hub", "commodities"),
    ("TTF=F", "TTF gas", "commodities"),
    ("GC=F", "Oro", "commodities"),
    ("HG=F", "Cobre", "commodities"),
    ("ZW=F", "Trigo", "commodities"),
    ("^VIX", "VIX", "rates"),
    ("^TNX", "UST 10a", "rates"),
    ("^FVX", "UST 5a", "rates"),
    ("BTC-USD", "Bitcoin", "crypto"),
]


async def fetch_quote(client: httpx.AsyncClient, symbol: str) -> dict[str, Any]:
    r = await client.get(
        CHART_URL.format(symbol=symbol),
        params={"range": "1mo", "interval": "1d"},
        headers={"User-Agent": "Mozilla/5.0 (compatible; TORNILLO-SUELTO/0.1)", "Accept": "application/json"},
    )
    r.raise_for_status()
    data = r.json()
    result = data["chart"]["result"][0]
    meta = result.get("meta", {})
    closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", []) or []
    timestamps = result.get("timestamp", []) or []
    history = [{"t": _ts(ts), "v": c} for ts, c in zip(timestamps, closes, strict=False) if c is not None]
    price = meta.get("regularMarketPrice")
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    if price is None and history:
        price = history[-1]["v"]
    if prev is None and len(history) >= 2:
        prev = history[-2]["v"]
    change_pct = ((price - prev) / prev * 100.0) if (price is not None and prev) else None
    observed = meta.get("regularMarketTime")
    observed_iso = _ts(observed) if observed else (history[-1]["t"] if history else None)
    return {
        "price": price,
        "change_pct": change_pct,
        "currency": meta.get("currency"),
        "observed_at": observed_iso,
        "history": history[-30:],
    }


async def refresh_markets(db: Database, client: httpx.AsyncClient) -> dict[str, Any]:
    ok, errors = 0, []
    ts = now_iso()
    for symbol, label, group in SYMBOLS:
        try:
            q = await fetch_quote(client, symbol)
            with db.tx() as conn:
                conn.execute(
                    """INSERT INTO market_quote(symbol, label, group_name, price, change_pct, currency, observed_at,
                       fetched_at, source, history, error) VALUES (?,?,?,?,?,?,?,?,?,?,NULL)
                       ON CONFLICT(symbol) DO UPDATE SET price=excluded.price, change_pct=excluded.change_pct,
                       currency=excluded.currency, observed_at=excluded.observed_at, fetched_at=excluded.fetched_at,
                       history=excluded.history, error=NULL""",
                    (
                        symbol,
                        label,
                        group,
                        q["price"],
                        q["change_pct"],
                        q["currency"],
                        q["observed_at"],
                        ts,
                        "Yahoo Finance (chart API)",
                        json.dumps(q["history"]),
                    ),
                )
            ok += 1
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as e:
            err = f"{type(e).__name__}: {str(e)[:120]}"
            errors.append(f"{symbol}: {err}")
            with db.tx() as conn:
                conn.execute(
                    """INSERT INTO market_quote(symbol, label, group_name, fetched_at, source, error)
                       VALUES (?,?,?,?,?,?)
                       ON CONFLICT(symbol) DO UPDATE SET error=excluded.error""",
                    (symbol, label, group, ts, "Yahoo Finance (chart API)", err),
                )
    return {"ok": ok, "errors": errors}
