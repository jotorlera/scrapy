"""Conectores: parseo de feeds con fixture, normalización, autodescubrimiento y presupuesto LLM."""

from __future__ import annotations

from atlas_core.connectors.base import RawItem
from atlas_core.connectors.rss import RSSConnector, feed_links_from_html, is_valid_feed, parse_feed
from atlas_core.util import canonicalize_url, clean_html, split_sentences

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
            "INSERT INTO llm_call(at, module, cost_usd, ok) VALUES (datetime('now'), 'test', 9.0, 1)"
        )
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
