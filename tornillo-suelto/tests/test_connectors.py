"""Conectores: parseo de feeds con fixture, normalización, autodescubrimiento y presupuesto LLM."""

from __future__ import annotations

import time

import httpx

from atlas_core.connectors.base import RawItem
from atlas_core.connectors.rss import (
    RSSConnector,
    feed_links_from_html,
    is_valid_feed,
    parse_feed,
    resolve_link,
)
from atlas_core.db import now_iso
from atlas_core.util import canonicalize_url, clean_html, split_sentences, to_iso

FEED = """<?xml version="1.0"?><rss version="2.0"><channel><title>Diario Test</title><language>es-ES</language>
<item><title>El BCE mantiene los tipos en el 2%</title><link>https://diario.test/bce?utm_source=rss&amp;id=7</link>
<description><![CDATA[<p>Lagarde afirm&oacute; que la inflaci&oacute;n sigue cerca del objetivo.</p><script>x()</script>]]></description>
<pubDate>Mon, 28 Sep 2026 10:00:00 GMT</pubDate><author>redaccion@diario.test (Redacción)</author></item>
<item><title></title><link>https://diario.test/vacio</link></item>
</channel></rss>""".encode()


def test_parse_and_normalize_feed_item():
    parsed = parse_feed(FEED)
    assert is_valid_feed(parsed) and len(parsed.entries) == 2
    conn = RSSConnector()
    source = {"id": "s1", "type": "newspaper", "languages": ["es"], "paywall": "none"}
    e = parsed.entries[0]
    item = RawItem(
        url=e.link,
        title=e.title,
        summary=e.summary,
        published_at="2026-09-28T10:00:00+00:00",
        authors=["Redacción"],
        lang="es",
    )
    doc = conn.normalize(source, item)
    assert doc is not None
    assert doc.canonical_url == "https://diario.test/bce?id=7"  # utm eliminado
    assert "Lagarde afirmó" in doc.lede and "<p>" not in doc.lede and "x()" not in doc.lede
    assert doc.kind == "article" and doc.lang == "es" and doc.content_hash
    assert conn.normalize(source, RawItem(url="https://diario.test/vacio", title="")) is None
    # defensa final: un enlace relativo nunca llega a document.url (UNIQUE entre medios)
    assert conn.normalize(source, RawItem(url="/article/1", title="Titular")) is None


def test_to_iso_struct_time_is_utc_whatever_the_local_timezone(monkeypatch):
    """feedparser entrega struct_time ya en UTC; con mktime (hora local) cada fecha se desplazaba 1-2 h fuera de UTC."""
    monkeypatch.setenv("TZ", "Europe/Madrid")
    time.tzset()
    try:
        assert to_iso(time.gmtime(1790000000)) == "2026-09-21T14:13:20+00:00"
        e = parse_feed(FEED).entries[0]
        assert to_iso(e.published_parsed) == to_iso(e.published) == "2026-09-28T10:00:00+00:00"
    finally:
        monkeypatch.undo()
        time.tzset()


MIXED_LINKS_FEED = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>TRT</title>
<item><title>Ruta absoluta</title><link>/article/1</link></item>
<item><title>Host de la fuente sin esquema</title><link>www.trtworld.com/article/2</link></item>
<item><title>Relativo al feed</title><link>rel/news.html</link></item>
<item><title>Sin esquema y no es un host propio</title><link>news.html</link></item>
<item><title>No http</title><link>mailto:redaccion@trtworld.com</link></item>
</channel></rss>"""


def test_resolve_link_cases():
    base = "https://www.trtworld.com/feed/rss.xml"
    assert resolve_link("/article/1", base) == "https://www.trtworld.com/article/1"
    assert resolve_link("rel/news.html", base) == "https://www.trtworld.com/feed/rel/news.html"
    assert (
        resolve_link("news.html", base) == "https://www.trtworld.com/feed/news.html"
    )  # no 'https://news.html'
    assert resolve_link("https://other.test/x?a=1", base) == "https://other.test/x?a=1"
    # caso real (bea): host sin esquema anclado al dominio de la fuente, no al del feed
    assert (
        resolve_link("www.bea.gov/news/2026/gdp", "https://apps.bea.gov/rss/rss.xml", "bea.gov")
        == "https://www.bea.gov/news/2026/gdp"
    )
    assert resolve_link("mailto:a@b.test", base) is None
    assert resolve_link("", base) is None and resolve_link(None, base) is None


async def test_fetch_resolves_relative_links_against_the_feed_url():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=MIXED_LINKS_FEED, headers={"content-type": "application/rss+xml"})

    source = {
        "id": "s1",
        "type": "broadcaster",
        "domain": "trtworld.com",
        "feeds": ["https://www.trtworld.com/feed/rss.xml"],
    }
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await RSSConnector().fetch(source, client)
    assert res.ok and [it.url for it in res.items] == [
        "https://www.trtworld.com/article/1",
        "https://www.trtworld.com/article/2",
        "https://www.trtworld.com/feed/rel/news.html",
        "https://www.trtworld.com/feed/news.html",
    ]


def test_kind_by_source_type():
    conn = RSSConnector()
    item = RawItem(url="https://ecb.test/pr", title="Monetary policy decisions", summary="text")
    assert conn.normalize({"id": "s", "type": "central_bank", "languages": ["en"]}, item).kind == "statement"
    assert conn.normalize({"id": "s", "type": "court", "languages": ["en"]}, item).kind == "court_ruling"


def test_feed_autodiscovery_from_html():
    html = '<html><head><link rel="alternate" type="application/rss+xml" href="/rss/portada.xml"><link rel="stylesheet" href="/a.css"><link rel="alternate" type="application/atom+xml" href="https://cdn.test/atom.xml"></head></html>'
    assert feed_links_from_html(html, "https://diario.test/") == [
        "https://diario.test/rss/portada.xml",
        "https://cdn.test/atom.xml",
    ]


def test_util_helpers():
    assert clean_html("<p>Hola&nbsp;<b>mundo</b></p><br>Adiós") == "Hola mundo\n\nAdiós"
    assert canonicalize_url("https://x.test/a?fbclid=1&b=2#frag") == "https://x.test/a?b=2"
    s = split_sentences(
        "El Sr. García habló en Madrid. Dijo que la reforma costará 3.000 millones. ¿Y ahora qué pasará con los presupuestos?"
    )
    assert len(s) == 3 and s[0].startswith("El Sr. García")


def test_llm_budget_state_without_key(db, monkeypatch):
    from atlas_core import llm as llm_mod

    monkeypatch.setattr(llm_mod.settings, "anthropic_api_key", None)
    llm = llm_mod.LLM(db)
    assert not llm.enabled
    st = llm.budget_state()
    assert st["daily_cap_usd"] == 10 and st["spent_today_usd"] == 0 and not st["hard_stop"]
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO llm_call(at, module, cost_usd, ok) VALUES (?, 'test', 9.0, 1)", (now_iso(),)
        )  # mismo formato ISO que el resto de columnas de fecha (nunca datetime de SQLite)
    st = llm.budget_state()
    assert st["pause_noncritical"] and not st["hard_stop"]
    try:
        llm.complete("bulk", "extractor", "x", module="test")
        raise AssertionError("debe fallar sin clave")
    except llm_mod.LLMUnavailable:
        pass
    assert llm.model_for("bulk").startswith("claude-")
    text, version = llm.load_prompt("editor_jefe")
    assert "Mandato" in text and version == "1"
    cost = llm_mod.Usage(input_tokens=1_000_000, output_tokens=0).cost("claude-haiku-4-5")
    assert cost == 1.0


def test_feed_language_code_is_validated():
    from atlas_core.connectors.rss import _lang_code

    assert _lang_code("es-ES") == "es" and _lang_code("EN") == "en" and _lang_code("zh_CN") == "zh"
    assert _lang_code("The Korea Herald") is None and _lang_code("") is None and _lang_code(None) is None
