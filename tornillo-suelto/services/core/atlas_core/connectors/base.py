"""Interfaz común de conectores: discover() → fetch() → normalize() → health()."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from ..settings import settings


@dataclass
class RawItem:
    url: str
    title: str = ""
    summary: str = ""
    content: str = ""
    published_at: str | None = None
    authors: list[str] = field(default_factory=list)
    lang: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class FetchResult:
    items: list[RawItem] = field(default_factory=list)
    ok: bool = True
    error: str | None = None
    status: int | None = None
    etag: str | None = None
    last_modified: str | None = None
    latency_ms: int = 0
    not_modified: bool = False
    feed_url: str | None = None


@dataclass
class DocumentIn:
    source_id: str
    url: str
    canonical_url: str
    kind: str
    title: str
    lede: str
    text: str
    lang: str | None
    authors: list[str]
    published_at: str | None
    content_hash: str
    extraction_method: str
    paywalled: bool
    meta: dict[str, Any]


class SourceConnector(Protocol):
    name: str

    async def discover(self, source: dict[str, Any], client: httpx.AsyncClient) -> list[str]: ...

    async def fetch(self, source: dict[str, Any], client: httpx.AsyncClient) -> FetchResult: ...

    def normalize(self, source: dict[str, Any], item: RawItem) -> DocumentIn | None: ...


def make_client(timeout: float = 20.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=10.0),
        follow_redirects=True,
        headers={
            "User-Agent": settings.atlas_user_agent,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html;q=0.8, */*;q=0.5",
            "Accept-Language": "es, en;q=0.9, fr;q=0.8, de;q=0.7",
        },
        limits=httpx.Limits(max_connections=settings.atlas_ingest_concurrency, max_keepalive_connections=8),
    )
