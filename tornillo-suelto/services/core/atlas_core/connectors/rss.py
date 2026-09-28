"""Conector RSS/Atom con ETag / If-Modified-Since y autodescubrimiento de feeds.

Reglas de ingesta (docs/spec/03 §6): User-Agent identificable, solo lo que publica el feed (titular, entradilla,
contenido si el medio lo incluye), sin saltarse muros de pago. El texto completo por scraping es opcional
(`extract` extra) y se respeta robots.txt; en esta fase no se activa por defecto.
"""

from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urljoin

import feedparser
import httpx

from ..util import canonicalize_url, clean_html, content_hash, to_iso, truncate
from .base import DocumentIn, FetchResult, RawItem

PRIMARY_TYPES = {"institution", "central_bank", "court", "statistical_office", "intl_org"}
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
KIND_BY_TYPE = {
    "central_bank": "statement",
    "court": "court_ruling",
    "statistical_office": "dataset_release",
    "institution": "official_doc",
    "intl_org": "official_doc",
    "academic": "paper",
    "think_tank": "article",
    "newsletter": "post",
}

COMMON_FEED_PATHS = (
    "/feed",
    "/feed/",
    "/rss",
    "/rss/",
    "/rss.xml",
    "/feed.xml",
    "/atom.xml",
    "/index.xml",
    "/feeds/posts/default",
    "/rss/portada",
    "/rss/news",
    "/feed/rss",
    "/?feed=rss2",
)

_LINK_RE = re.compile(r"<link[^>]+>", re.I)
_ATTR_RE = re.compile(r'(\w[\w:-]*)\s*=\s*"([^"]*)"|(\w[\w:-]*)\s*=\s*\'([^\']*)\'', re.I)


def _attrs(tag: str) -> dict[str, str]:
    out = {}
    for m in _ATTR_RE.finditer(tag):
        k = (m.group(1) or m.group(3) or "").lower()
        v = m.group(2) if m.group(2) is not None else m.group(4)
        out[k] = v or ""
    return out


def feed_links_from_html(html_text: str, base_url: str) -> list[str]:
    found = []
    for tag in _LINK_RE.findall(html_text or ""):
        a = _attrs(tag)
        rel = a.get("rel", "").lower()
        typ = a.get("type", "").lower()
        href = a.get("href")
        if "alternate" in rel and href and ("rss" in typ or "atom" in typ or "xml" in typ):
            found.append(urljoin(base_url, href))
    # sin duplicados, en orden
    seen, out = set(), []
    for f in found:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def parse_feed(content: bytes | str) -> feedparser.FeedParserDict:
    return feedparser.parse(content)


def is_valid_feed(parsed: feedparser.FeedParserDict) -> bool:
    return bool(getattr(parsed, "entries", None)) and len(parsed.entries) > 0


class RSSConnector:
    name = "rss"

    async def discover(self, source: dict[str, Any], client: httpx.AsyncClient) -> list[str]:
        domain = source.get("domain") or ""
        if not domain:
            return []
        base = domain if domain.startswith("http") else f"https://{domain}"
        candidates: list[str] = []
        try:
            r = await client.get(base, headers={"Accept": "text/html"})
            if r.status_code < 400 and "html" in r.headers.get("content-type", ""):
                candidates.extend(feed_links_from_html(r.text[:400_000], str(r.url)))
        except (httpx.HTTPError, ValueError):
            pass
        for p in COMMON_FEED_PATHS:
            candidates.append(urljoin(base + "/", p.lstrip("/")))
        valid: list[str] = []
        seen: set[str] = set()
        for url in candidates:
            if url in seen or len(valid) >= 2:
                continue
            seen.add(url)
            try:
                r = await client.get(url)
                if r.status_code >= 400 or len(r.content) < 200:
                    continue
                ctype = r.headers.get("content-type", "")
                if "html" in ctype and b"<rss" not in r.content[:2000] and b"<feed" not in r.content[:2000]:
                    continue
                parsed = parse_feed(r.content)
                if is_valid_feed(parsed):
                    valid.append(str(r.url))
            except (httpx.HTTPError, ValueError):
                continue
        return valid

    async def fetch(self, source: dict[str, Any], client: httpx.AsyncClient) -> FetchResult:
        feeds: list[str] = list(source.get("feeds") or [])
        if not feeds:
            return FetchResult(ok=False, error="sin feed configurado")
        result = FetchResult()
        errors = []
        t0 = time.monotonic()
        for feed_url in feeds[:3]:
            headers = {}
            if source.get("etag") and len(feeds) == 1:
                headers["If-None-Match"] = source["etag"]
            if source.get("last_modified") and len(feeds) == 1:
                headers["If-Modified-Since"] = source["last_modified"]
            try:
                r = await client.get(feed_url, headers=headers)
                if r.status_code in (403, 406, 429):
                    # algunos servidores rechazan agentes desconocidos: segundo intento con UA de navegador
                    r = await client.get(feed_url, headers={**headers, "User-Agent": BROWSER_UA})
            except httpx.HTTPError as e:  # red, timeout, TLS
                errors.append(f"{feed_url}: {type(e).__name__}")
                continue
            result.status = r.status_code
            result.feed_url = feed_url
            if r.status_code == 304:
                result.not_modified = True
                continue
            if r.status_code >= 400:
                errors.append(f"{feed_url}: HTTP {r.status_code}")
                continue
            parsed = parse_feed(r.content)
            if not is_valid_feed(parsed):
                errors.append(f"{feed_url}: sin entradas")
                continue
            result.etag = r.headers.get("etag") or result.etag
            result.last_modified = r.headers.get("last-modified") or result.last_modified
            feed_lang = (parsed.feed.get("language") or "").split("-")[0].lower() or None
            for e in parsed.entries[:120]:
                link = e.get("link") or ""
                if not link:
                    continue
                content = ""
                if e.get("content"):
                    try:
                        content = e["content"][0].get("value", "")
                    except (KeyError, IndexError, TypeError):
                        content = ""
                summary = e.get("summary", "") or e.get("description", "")
                published = e.get("published_parsed") or e.get("updated_parsed") or e.get("created_parsed")
                authors = []
                if e.get("authors"):
                    authors = [a.get("name") for a in e["authors"] if isinstance(a, dict) and a.get("name")]
                elif e.get("author"):
                    authors = [e["author"]]
                tags = [t.get("term") for t in e.get("tags", []) if isinstance(t, dict) and t.get("term")]
                result.items.append(
                    RawItem(
                        url=link,
                        title=clean_html(e.get("title", "")),
                        summary=summary,
                        content=content,
                        published_at=to_iso(published) or to_iso(e.get("published") or e.get("updated")),
                        authors=authors[:5],
                        lang=feed_lang,
                        meta={"tags": tags[:10], "feed": feed_url},
                    )
                )
        result.latency_ms = int((time.monotonic() - t0) * 1000)
        if not result.items and not result.not_modified:
            result.ok = False
            result.error = "; ".join(errors) or "sin entradas"
        elif errors:
            result.error = "; ".join(errors)
        return result

    def normalize(self, source: dict[str, Any], item: RawItem) -> DocumentIn | None:
        title = (item.title or "").strip()
        if not title or not item.url:
            return None
        lede = truncate(clean_html(item.summary), 600)
        text = clean_html(item.content) if item.content else ""
        if not text or len(text) < len(lede):
            text = lede
        # El feed puede repetir el titular en la entradilla: se evita duplicar
        if lede and lede.lower().startswith(title.lower()):
            lede = lede[len(title) :].lstrip(" .:–-—") or lede
        stype = source.get("type", "newspaper")
        kind = KIND_BY_TYPE.get(stype, "article")
        langs = source.get("languages") or []
        lang = item.lang or (langs[0] if langs else None)
        canonical = canonicalize_url(item.url)
        return DocumentIn(
            source_id=source["id"],
            url=item.url,
            canonical_url=canonical,
            kind=kind,
            title=title,
            lede=lede,
            text=truncate(text, 20_000),
            lang=lang,
            authors=item.authors,
            published_at=item.published_at,
            content_hash=content_hash(title, lede[:200]),
            extraction_method="feed",
            paywalled=(source.get("paywall") or "none") == "hard",
            meta=item.meta,
        )
