"""ARCHIVO: análogos históricos por similitud (embeddings locales) con tabla de coincidencias y diferencias."""

from __future__ import annotations

from typing import Any

import numpy as np

from ..db import Database, blob_to_vec, loads, vec_to_blob
from ..embed import get_embedder


def embed_cases(db: Database) -> int:
    emb = get_embedder()
    rows = db.all("SELECT id, name, category, summary, outcome, embedding_model FROM historical_case")
    n = 0
    with db.tx() as conn:
        for r in rows:
            if r["embedding_model"] == emb.name:
                continue
            v = emb.embed(f"{r['name']}. {r['category']}. {r['summary']} {r['outcome']}")
            conn.execute(
                "UPDATE historical_case SET embedding = ?, embedding_model = ? WHERE id = ?",
                (vec_to_blob(v), emb.name, r["id"]),
            )
            n += 1
    return n


def analogs(
    db: Database, query_text: str, top_n: int = 4, category: str | None = None
) -> list[dict[str, Any]]:
    emb = get_embedder()
    q = emb.embed(query_text)
    sql = "SELECT * FROM historical_case WHERE embedding IS NOT NULL AND embedding_model = ?"
    params: list[Any] = [emb.name]
    if category:
        sql += " AND category = ?"
        params.append(category)
    rows = db.all(sql, params)
    scored = []
    for r in rows:
        v = blob_to_vec(r["embedding"])
        if v is None:
            continue
        s = float(np.dot(q, v) / ((np.linalg.norm(q) * np.linalg.norm(v)) + 1e-9))
        d = dict(r)
        d.pop("embedding", None)
        d["countries"] = loads(d.get("countries"), [])
        d["variables"] = loads(d.get("variables"), {})
        d["sources"] = loads(d.get("sources"), [])
        d["similarity"] = round(s, 3)
        scored.append(d)
    scored.sort(key=lambda d: -d["similarity"])
    return scored[:top_n]


def compare_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Tabla de similitudes y diferencias sobre las variables codificadas."""
    keys: list[str] = []
    for c in cases:
        for k in c.get("variables") or {}:
            if k not in keys:
                keys.append(k)
    rows = []
    for k in keys:
        vals = [(c.get("variables") or {}).get(k) for c in cases]
        distinct = {str(v) for v in vals if v is not None}
        rows.append({"variable": k, "values": vals, "agree": len(distinct) <= 1})
    return {
        "variables": rows,
        "outcomes": [
            {"name": c["name"], "outcome": c.get("outcome"), "duration_months": c.get("duration_months")}
            for c in cases
        ],
    }
