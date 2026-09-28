"""Conectores de red con respuestas simuladas (httpx.MockTransport, sin red): cinta de mercados, mercados de
predicción, RSSConnector.fetch (304, reintento con UA de navegador, tope de tamaño) e insert_documents."""

from __future__ import annotations

import json

import httpx
import pytest

from atlas_core.connectors.base import DocumentIn
from atlas_core.connectors.rss import BROWSER_UA, FeedTooLarge, RSSConnector, get_bounded
from atlas_core.pipeline import insert_documents
from atlas_core.util import canonicalize_url
from conftest import make_source

FEED = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>
<item><title>Titular uno</title><link>https://t.example/1</link><description>Entradilla</description></item>
</channel></rss>"""

RSS_SOURCE = {"id": "s", "type": "newspaper", "domain": "t.example", "feeds": ["https://t.example/feed"]}


# ───────── cinta de mercados ─────────


async def test_refresh_markets_keeps_last_price_and_records_error(db):
    from atlas_core.connectors import markets as mk

    def ok(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("^IBEX"):
            return httpx.Response(
                200,
                json={
                    "chart": {
                        "result": [
                            {
                                "meta": {
                                    "regularMarketPrice": 15000.5,
                                    "chartPreviousClose": 14850.0,
                                    "currency": "EUR",
                                    "regularMarketTime": 1790000000,
                                },
                                "timestamp": [1789900000, 1790000000],
                                "indicators": {"quote": [{"close": [14850.0, 15000.5]}]},
                            }
                        ]
                    }
                },
            )
        return httpx.Response(404, json={"chart": {"result": None}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(ok)) as c:
        st = await mk.refresh_markets(db, c)
    assert st["ok"] == 1 and len(st["errors"]) == len(mk.SYMBOLS) - 1
    q = db.one(
        "SELECT price, change_pct, currency, observed_at, error, history FROM market_quote WHERE symbol='^IBEX'"
    )
    assert q["price"] == 15000.5 and q["change_pct"] == pytest.approx(1.0135, abs=1e-3)
    assert q["currency"] == "EUR" and q["observed_at"] == "2026-09-21T14:13:20+00:00" and q["error"] is None
    assert [h["v"] for h in json.loads(q["history"])] == [14850.0, 15000.5]
    # la serie falla: se conserva el último dato válido y se anota el error (nunca un dato inventado)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500))) as c:
        st = await mk.refresh_markets(db, c)
    assert st["ok"] == 0 and len(st["errors"]) == len(mk.SYMBOLS)
    q = db.one("SELECT price, change_pct, observed_at, error FROM market_quote WHERE symbol='^IBEX'")
    assert q["price"] == 15000.5 and q["observed_at"] == "2026-09-21T14:13:20+00:00"
    assert q["error"].startswith("HTTPStatusError")


# ───────── mercados de predicción ─────────


async def test_prediction_markets_parse_filter_and_store(db):
    from atlas_core.connectors import prediction_markets as pm

    def h(req: httpx.Request) -> httpx.Response:
        if req.url.host == "gamma-api.polymarket.com":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "1",
                        "question": "Will the ECB cut rates in October?",
                        "outcomes": '["Yes","No"]',
                        "outcomePrices": '["0.62","0.38"]',
                        "volumeNum": 1000,
                        "slug": "ecb-cut",
                        "endDate": "2026-10-30T00:00:00Z",
                    },
                    {
                        "id": "2",
                        "question": "Will Taylor Swift release an album?",
                        "outcomes": '["Yes","No"]',
                        "outcomePrices": '["0.9","0.1"]',
                    },
                    {"id": "3", "question": "Broken", "outcomePrices": "not json"},
                    {"id": "4", "question": ""},
                ],
            )
        if req.url.params.get("term") == "election":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "m1",
                        "outcomeType": "BINARY",
                        "probability": 0.4,
                        "question": "Spain election before 2027?",
                        "url": "https://manifold.markets/x",
                    },
                    {"id": "m2", "outcomeType": "MULTIPLE_CHOICE", "question": "x"},
                ],
            )
        return httpx.Response(429)  # el resto de términos: tolerado, no aborta

    async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
        assert await pm.refresh_prediction_markets(db, c) == {"polymarket": 1, "manifold": 1, "errors": []}
    rows = {r["id"]: dict(r) for r in db.all("SELECT * FROM prediction_market")}
    assert rows["polymarket:1"]["probability"] == 0.62 and rows["polymarket:1"]["url"].endswith("/ecb-cut")
    assert rows["polymarket:1"]["close_at"] == "2026-10-30T00:00:00Z" and "polymarket:2" not in rows
    assert rows["manifold:m1"]["probability"] == 0.4 and json.loads(rows["manifold:m1"]["tags"]) == [
        "election"
    ]


# ───────── RSSConnector.fetch ─────────


async def test_rss_fetch_returns_not_modified_on_304():
    def h(req: httpx.Request) -> httpx.Response:
        if req.headers.get("if-none-match") == '"abc"':
            return httpx.Response(304)
        return httpx.Response(200, content=FEED, headers={"etag": '"abc"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
        res = await RSSConnector().fetch({**RSS_SOURCE, "etag": '"abc"'}, c)
    assert res.not_modified and res.ok and res.items == [] and res.status == 304 and res.error is None


async def test_rss_fetch_retries_with_browser_ua_and_propagates_validators():
    agents: list[str | None] = []

    def h(req: httpx.Request) -> httpx.Response:
        agents.append(req.headers.get("user-agent"))
        if len(agents) == 1:
            return httpx.Response(403)
        return httpx.Response(
            200, content=FEED, headers={"etag": '"e1"', "last-modified": "Mon, 28 Sep 2026 10:00:00 GMT"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(h), headers={"User-Agent": "TORNILLO"}) as c:
        res = await RSSConnector().fetch(RSS_SOURCE, c)
    assert agents == ["TORNILLO", BROWSER_UA]
    assert res.ok and res.status == 200 and len(res.items) == 1
    assert res.etag == '"e1"' and res.last_modified == "Mon, 28 Sep 2026 10:00:00 GMT"


async def test_rss_fetch_invalid_url_is_a_source_error_not_an_exception():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))) as c:
        res = await RSSConnector().fetch({**RSS_SOURCE, "feeds": ["https://[::1/rss"]}, c)
    assert not res.ok and "InvalidURL" in res.error


async def test_feed_body_size_is_bounded(monkeypatch):
    from atlas_core.connectors import rss

    monkeypatch.setattr(rss.settings, "atlas_max_feed_bytes", 10_000)

    def h(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/by-header":
            return httpx.Response(
                200, headers={"content-length": "99999999"}, stream=httpx.ByteStream(b"<rss/>")
            )
        return httpx.Response(
            200, content=b"<rss>" + b"x" * 20_000
        )  # 774 KB gzip → 55 MB: se aborta al vuelo

    async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
        with pytest.raises(FeedTooLarge):
            await get_bounded(c, "https://t.example/by-header")
        with pytest.raises(FeedTooLarge):
            await get_bounded(c, "https://t.example/by-body")
        r, body = await get_bounded(c, "https://t.example/by-body", max_bytes=100_000)
        assert r.status_code == 200 and len(body) == 20_005
        res = await RSSConnector().fetch({**RSS_SOURCE, "feeds": ["https://t.example/by-body"]}, c)
    assert not res.ok and "FeedTooLarge" in res.error


# ───────── insert_documents ─────────


def _doc(sid: str, url: str, content_hash: str = "h1", title: str = "Titular de prueba") -> DocumentIn:
    return DocumentIn(
        source_id=sid,
        url=url,
        canonical_url=canonicalize_url(url),
        kind="article",
        title=title,
        lede="Entradilla",
        text="Texto",
        lang="es",
        authors=[],
        published_at=None,
        content_hash=content_hash,
        extraction_method="feed",
        paywalled=False,
        meta={},
    )


def test_insert_documents_dedups_by_canonical_url_and_content_hash(db):
    sid = make_source(db, "diario")
    docs = [
        _doc(sid, "https://d.example/a?utm_source=rss"),
        _doc(sid, "https://d.example/a?utm_medium=mail", content_hash="h2"),  # misma canonical_url
        _doc(sid, "https://d.example/otra", content_hash="h1"),  # mismo content_hash y misma fuente
        None,
    ]
    assert insert_documents(db, {"id": sid}, docs) == (1, 2)
    assert (
        db.scalar("SELECT COUNT(*) FROM document") == 1
        and db.scalar("SELECT COUNT(*) FROM document_fts") == 1
    )
    assert db.one("SELECT canonical_url FROM document")["canonical_url"] == "https://d.example/a"
    # el mismo hash desde OTRA fuente sí es un documento distinto
    other = make_source(db, "otro")
    assert insert_documents(db, {"id": other}, [_doc(other, "https://o.example/a", content_hash="h1")]) == (
        1,
        0,
    )


async def test_same_relative_path_from_two_sources_yields_two_documents(db):
    body = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
    <item><title>Titular compartido por ambos medios</title><link>/article/1</link></item></channel></rss>"""
    s1 = make_source(db, "trt", feeds=["https://www.trt.example/feed/rss.xml"])
    s2 = make_source(db, "nhk", feeds=["https://www.nhk.example/rss.xml"])
    conn = RSSConnector()
    total = 0
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body))
    ) as c:
        for sid in (s1, s2):
            src = dict(db.one("SELECT * FROM source WHERE id = ?", (sid,)))
            src["feeds"] = json.loads(src["feeds"])
            res = await conn.fetch(src, c)
            new, _dup = insert_documents(db, src, [conn.normalize(src, it) for it in res.items])
            total += new
    assert total == 2
    assert sorted(r["url"] for r in db.all("SELECT url FROM document")) == [
        "https://www.nhk.example/article/1",
        "https://www.trt.example/article/1",
    ]
