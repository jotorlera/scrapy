"""Utilidades pequeñas y sin dependencias del resto: limpieza de HTML, fechas, frases, hashes."""

from __future__ import annotations

import calendar
import hashlib
import html
import re
from datetime import UTC, datetime
from time import struct_time

from dateutil import parser as dateparser

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_NL_RE = re.compile(r"\n{3,}")


def clean_html(raw: str | None) -> str:
    """Convierte HTML en texto plano legible (párrafos separados por salto de línea)."""
    if not raw:
        return ""
    s = raw
    s = re.sub(r"(?is)<(script|style|noscript|iframe|figure|svg)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)<\s*(/p|/div|/h[1-6]|/tr|/blockquote)\s*>", "\n\n", s)
    s = re.sub(r"(?i)<\s*(br|/li)\s*/?>", "\n", s)
    s = _TAG_RE.sub(" ", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = _WS_RE.sub(" ", s)
    s = "\n".join(line.strip() for line in s.split("\n"))
    s = _NL_RE.sub("\n\n", s)
    return s.strip()


def to_iso(value) -> str | None:
    """Acepta struct_time, datetime o str y devuelve ISO-8601 en UTC (o None)."""
    if value is None:
        return None
    try:
        if isinstance(value, struct_time):
            # feedparser entrega struct_time ya en UTC: timegm lo interpreta como UTC (mktime lo haría como hora
            # local y desplazaría cada fecha 1-2 h en cualquier máquina que no esté en UTC)
            dt = datetime.fromtimestamp(calendar.timegm(value), tz=UTC)
        elif isinstance(value, datetime):
            dt = value if value.tzinfo else value.replace(tzinfo=UTC)
        else:
            dt = dateparser.parse(str(value))
            if dt is None:
                return None
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).replace(microsecond=0).isoformat()
    except (ValueError, TypeError, OverflowError):
        return None


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


def content_hash(*parts: str | None) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update((p or "").strip().lower().encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()[:32]


_SENT_RE = re.compile(r"(?<=[.!?…])\s+(?=[A-ZÁÉÍÓÚÑÜ¿¡\"“«(])")
_ABBR = (
    "Sr.",
    "Sra.",
    "Dr.",
    "Dra.",
    "EE. UU.",
    "Mr.",
    "Mrs.",
    "Ms.",
    "St.",
    "vs.",
    "Inc.",
    "Ltd.",
    "No.",
    "Nº.",
)


def split_sentences(text: str) -> list[str]:
    """División de frases sencilla y conservadora (es/en/fr/de/it/pt)."""
    if not text:
        return []
    t = text.replace("\n", " ")
    for a in _ABBR:
        t = t.replace(a, a.replace(".", "․"))
    parts = _SENT_RE.split(t)
    out = []
    for p in parts:
        p = p.replace("․", ".").strip()
        if len(p) >= 25:
            out.append(p)
    return out


def truncate(s: str | None, n: int) -> str:
    if not s:
        return ""
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def domain_of(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url or "")
    d = (m.group(1) if m else "").lower()
    return d[4:] if d.startswith("www.") else d


def canonicalize_url(url: str) -> str:
    """Quita parámetros de seguimiento y fragmentos. Conserva el resto tal cual."""
    if not url:
        return url
    url = url.split("#", 1)[0]
    if "?" in url:
        base, qs = url.split("?", 1)
        keep = []
        for kv in qs.split("&"):
            k = kv.split("=", 1)[0].lower()
            if k.startswith("utm_") or k in {
                "fbclid",
                "gclid",
                "ref",
                "ref_src",
                "s",
                "mc_cid",
                "mc_eid",
                "ns_campaign",
                "ns_mchannel",
                "ns_source",
                "cmpid",
                "ocid",
                "at_medium",
                "at_campaign",
                "xtor",
                "smid",
                "partner",
                "ico",
                "srnd",
                "sref",
            }:
                continue
            keep.append(kv)
        url = base + ("?" + "&".join(keep) if keep else "")
    return url
