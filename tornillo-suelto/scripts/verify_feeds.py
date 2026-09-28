"""Verifica los feeds de config/feeds.yaml y autodescubre los que faltan. Uso: python scripts/verify_feeds.py

Imprime un informe y escribe data/feeds_verified.yaml con los feeds que responden con entradas.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "core"))

from atlas_core.config_loader import feeds_catalog, sources_seed  # noqa: E402
from atlas_core.connectors.base import make_client  # noqa: E402
from atlas_core.connectors.rss import RSSConnector  # noqa: E402


async def main() -> None:
    seeds = sources_seed()
    catalog = feeds_catalog()
    conn = RSSConnector()
    sem = asyncio.Semaphore(16)
    results: dict[str, dict] = {}

    async def check(src: dict) -> None:
        slug = src["slug"]
        if src.get("t") == "data_api":
            return
        source = {
            "id": slug,
            "slug": slug,
            "domain": src.get("domain"),
            "type": src.get("t"),
            "feeds": catalog.get(slug, []),
        }
        async with sem, make_client(timeout=20.0) as client:
            if source["feeds"]:
                res = await conn.fetch(source, client)
                if res.ok and res.items:
                    results[slug] = {"feeds": [res.feed_url], "items": len(res.items), "how": "curated"}
                    return
            discovered = await conn.discover(source, client)
            if discovered:
                source["feeds"] = discovered[:1]
                res = await conn.fetch(source, client)
                if res.ok and res.items:
                    results[slug] = {"feeds": discovered[:1], "items": len(res.items), "how": "discovered"}
                    return
            results[slug] = {
                "feeds": [],
                "items": 0,
                "how": "none",
                "error": getattr(res, "error", None) if source["feeds"] else "no feed found",
            }

    await asyncio.gather(*(check(s) for s in seeds))
    ok = {k: v for k, v in results.items() if v["items"]}
    bad = {k: v for k, v in results.items() if not v["items"]}
    print(f"OK: {len(ok)} · sin feed: {len(bad)}")
    for k, v in sorted(ok.items()):
        print(f"  ✓ {k:24s} {v['how']:10s} {v['items']:4d}  {v['feeds'][0]}")
    for k, v in sorted(bad.items()):
        print(f"  ✗ {k:24s} {v.get('error')}")
    out = {k: v["feeds"][0] for k, v in sorted(ok.items())}
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "feeds_verified.yaml").write_text(
        yaml.safe_dump(out, allow_unicode=True, sort_keys=True), encoding="utf-8"
    )


if __name__ == "__main__":
    asyncio.run(main())
