from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "core"))
os.environ.setdefault("ATLAS_SCHEDULER", "0")

from atlas_core.db import Database, set_db  # noqa: E402


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    d = Database(tmp_path / "test.db")
    _ = d.conn  # crea el esquema
    set_db(d)
    return d


@pytest.fixture()
def seeded(db: Database) -> Database:
    from atlas_core.seed import seed_all

    seed_all(db)
    return db


def make_source(db: Database, slug: str, **kw) -> str:
    from atlas_core.db import dumps, new_id, now_iso

    sid = new_id()
    row = {
        "id": sid,
        "slug": slug,
        "name": kw.get("name", slug.title()),
        "domain": f"{slug}.example",
        "type": kw.get("type", "newspaper"),
        "tier": kw.get("tier", 2),
        "country": kw.get("country", "ES"),
        "languages": dumps(kw.get("languages", ["es"])),
        "region_bloc": kw.get("bloc", "es"),
        "state_relation": kw.get("state_relation", "independent"),
        "ideology_label": kw.get("ideology", "center"),
        "paywall": "none",
        "feeds": dumps(kw.get("feeds", [f"https://{slug}.example/feed"])),
        "feed_status": "curated",
        "active": 1,
        "poll_minutes": 30,
        "review_status": "seed_unverified",
        "group_name": "test",
        "created_at": now_iso(),
    }
    db.insert("source", row)
    return sid


def make_doc(
    db: Database,
    source_id: str,
    title: str,
    lede: str = "",
    text: str = "",
    published_at: str | None = None,
    url: str | None = None,
) -> str:
    from atlas_core.db import dumps, new_id, now_iso
    from atlas_core.util import content_hash

    did = new_id()
    ts = published_at or now_iso()
    db.insert(
        "document",
        {
            "id": did,
            "source_id": source_id,
            "kind": "article",
            "url": url or f"https://x.example/{did}",
            "canonical_url": url or f"https://x.example/{did}",
            "title": title,
            "lede": lede,
            "text": text or lede,
            "lang": "es",
            "authors": dumps([]),
            "published_at": ts,
            "fetched_at": ts,
            "content_hash": content_hash(title, lede),
            "extraction_method": "feed",
            "paywalled": 0,
            "countries": dumps([]),
            "meta": dumps({}),
        },
    )
    db.exec(
        "INSERT INTO document_fts(doc_id, title, lede, text) VALUES (?,?,?,?)",
        (did, title, lede, text or lede),
    )
    return did
