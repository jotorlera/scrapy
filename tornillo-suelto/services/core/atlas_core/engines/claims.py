"""Afirmaciones con cita ("cita o descarta"), docs/spec/07 §3.

Dos extractores:
- `heuristic_claims`: sin LLM. Frases del titular y la entradilla; la afirmación ES la cita literal. Nivel por
  reglas (data si hay cifras; opinion si hay marcadores). Etiqueta `heuristic:v1`.
- Las salidas del extractor LLM pasan por `quote_supported` antes de persistirse: si la cita no está en el texto,
  la afirmación se descarta (no se marca: se descarta).

Canonicalización: dentro de un evento, una afirmación nueva con similitud ≥ 0,82 con otra existente se convierte
en `claim_evidence` de esa afirmación (fuente adicional) en vez de crear una nueva.
Estado: `confirmed` si hay primaria (tier 1) o ≥ 2 fuentes independientes de tier ≤ 2; si no, `unverified`.
Cada cambio de estado genera `claim_revision`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..db import Database, blob_to_vec, dumps, loads, new_id, now_iso, vec_to_blob
from ..embed import cosine, get_embedder, normalize_text
from ..util import split_sentences, truncate

HEURISTIC_VERSION = "heuristic:v1"
CANON_THRESHOLD = 0.82
MAX_CLAIMS_PER_DOC = 4

_NUM_RE = re.compile(r"\d[\d.,]*\s?(%|por ciento|percent|millones|millions|billion|billones|mil|thousand|€|\$|£|pb|bp|puntos|points|muertos|killed|dead|heridos|injured)|\b\d{2,}\b")
_OPINION_RE = re.compile(
    r"\b(debería|deberían|debe(?:mos)?|hay que|opinión|editorial|creo|pienso|a mi juicio|should|must|ought|in my view|opinion|análisis:|columna|tribuna|op-ed|why .* is wrong|why .* matters)\b",
    re.I,
)
_ATTR_RE = re.compile(
    r"(?:según|de acuerdo con|according to|selon|laut|secondo)\s+([^,.;:()\n]{3,70}?)(?=[,.;:]|\s+(?:que|qui|dass|who|which)\b|$)",
    re.I,
)
_ARTICLES = ("el ", "la ", "los ", "las ", "the ", "le ", "les ", "der ", "die ", "das ", "il ", "lo ", "un ", "una ", "a ", "an ")
_SAID_RE = re.compile(
    r"([A-ZÁÉÍÓÚÑÜ][\w.\-]*(?:\s+[A-ZÁÉÍÓÚÑÜ][\w.\-]*){0,3})\s+(?:dijo|afirmó|aseguró|declaró|anunció|advirtió|señaló|said|says|announced|declared|warned|told|stated|a déclaré|a annoncé|sagte|erklärte)\b",
)
_QUESTION_RE = re.compile(r"\?\s*$")


@dataclass
class ClaimCandidate:
    text: str
    quote: str
    level: str
    check_worthy: float
    attributed_to: str | None = None
    extracted_by: str = HEURISTIC_VERSION
    meta: dict[str, Any] = field(default_factory=dict)


def quote_supported(quote: str, text: str) -> bool:
    """La cita debe aparecer literalmente (ignorando mayúsculas, acentos y espacios) en el texto."""
    if not quote or not text:
        return False
    q = re.sub(r"\s+", " ", normalize_text(quote)).strip(" .\"'“”«»")
    t = re.sub(r"\s+", " ", normalize_text(text))
    if len(q) < 12:
        return False
    return q in t


def _level_for(sentence: str, source: dict[str, Any], is_title: bool) -> str:
    if _OPINION_RE.search(sentence) or _QUESTION_RE.search(sentence):
        return "opinion"
    if source.get("type") in ("magazine", "newsletter", "think_tank") and not _NUM_RE.search(sentence) and not is_title:
        return "opinion"
    if source.get("type") == "academic":
        return "academic"
    if _NUM_RE.search(sentence):
        return "data"
    return "fact"


def _attribution(sentence: str) -> str | None:
    m = _ATTR_RE.search(sentence)
    if m:
        who = m.group(1).strip(" ,.;:")
        low = who.lower()
        for a in _ARTICLES:
            if low.startswith(a):
                who = who[len(a):]
                break
        if who and len(who.split()) <= 8:
            return truncate(who, 60)
    m = _SAID_RE.search(sentence)
    if m:
        cand = m.group(1).strip()
        if cand.lower() not in {"el", "la", "the", "un", "una", "a", "an"}:
            return truncate(cand, 60)
    return None


def heuristic_claims(doc: dict[str, Any], source: dict[str, Any]) -> list[ClaimCandidate]:
    """Frases literales del documento como afirmaciones candidatas. La cita es la propia frase."""
    out: list[ClaimCandidate] = []
    title = (doc.get("title") or "").strip()
    lede = (doc.get("lede") or "").strip()
    text = doc.get("text") or ""
    full = "\n".join(p for p in (title, lede, text) if p)
    seen: set[str] = set()

    institutional = source.get("type") in ("institution", "central_bank", "court", "statistical_office", "intl_org")

    def add(sentence: str, is_title: bool) -> None:
        s = sentence.strip()
        key = normalize_text(s)[:120]
        words = [w for w in s.split() if any(ch.isalpha() for ch in w)]
        if len(s) < 40 or len(words) < 6 or key in seen or len(out) >= MAX_CLAIMS_PER_DOC:
            return
        letters = sum(ch.isalpha() for ch in s)
        if letters < 0.6 * len(s.replace(" ", "")):
            return  # listados, códigos, tablas
        if not quote_supported(s, full):
            return
        seen.add(key)
        level = _level_for(s, source, is_title)
        attributed = _attribution(s)
        if attributed is None and institutional:
            attributed = source.get("name")  # lo que dice una institución se atribuye a la institución
        cw = 0.35
        if level == "data":
            cw = 0.8
        elif attributed:
            cw = 0.6
        if is_title:
            cw += 0.1
        if level == "opinion":
            cw = 0.15
        out.append(ClaimCandidate(text=s, quote=truncate(s, 300), level=level, check_worthy=min(1.0, cw), attributed_to=attributed))

    if title:
        add(title, True)
    for s in split_sentences(lede)[:3]:
        add(s, False)
    if len(out) < MAX_CLAIMS_PER_DOC and text and text != lede:
        for s in split_sentences(text)[:6]:
            add(s, False)
    return out


def _independent_sources(evidence_rows: list[dict[str, Any]]) -> tuple[int, bool]:
    """Nº de fuentes independientes de tier ≤ 2 y si hay primaria (tier 1). Dos medios que citan la misma agencia
    no cuentan como independientes (heurística: mismo texto de cita → mismo origen)."""
    seen_quotes: set[str] = set()
    independent: set[str] = set()
    primary = False
    for ev in evidence_rows:
        tier = ev.get("tier") or 4
        if tier == 1:
            primary = True
        if tier <= 2:
            qkey = normalize_text(ev.get("quote") or "")[:80]
            if qkey in seen_quotes:
                continue
            seen_quotes.add(qkey)
            independent.add(ev["source_id"])
    return len(independent), primary


def compute_status(evidence_rows: list[dict[str, Any]]) -> str:
    n_indep, primary = _independent_sources(evidence_rows)
    refutes = [e for e in evidence_rows if e.get("stance") == "refutes"]
    supports = [e for e in evidence_rows if e.get("stance") in ("supports", "mentions")]
    if refutes and supports:
        return "disputed"
    if refutes and not supports:
        return "refuted"
    if primary or n_indep >= 2:
        return "confirmed"
    return "unverified"


def persist_claims(
    db: Database,
    doc: dict[str, Any],
    source: dict[str, Any],
    event_id: str | None,
    candidates: list[ClaimCandidate],
) -> dict[str, int]:
    """Guarda afirmaciones canonicalizando dentro del evento. Devuelve contadores."""
    stats = {"new": 0, "merged": 0, "dropped": 0, "status_changes": 0}
    if not candidates:
        return stats
    emb = get_embedder()
    full_text = "\n".join(p for p in (doc.get("title"), doc.get("lede"), doc.get("text")) if p)
    existing: list[tuple[str, np.ndarray]] = []
    if event_id:
        rows = db.all(
            "SELECT c.id, c.text_canonical FROM claim c WHERE c.event_id = ? ORDER BY c.created_at DESC LIMIT 200",
            (event_id,),
        )
        texts = [r["text_canonical"] for r in rows]
        if texts:
            vecs = emb.embed_many(texts)
            existing = [(r["id"], vecs[i]) for i, r in enumerate(rows)]
    ts = now_iso()
    with db.tx() as conn:
        for cand in candidates:
            if not quote_supported(cand.quote, full_text):
                stats["dropped"] += 1
                continue
            vec = emb.embed(cand.text)
            target_claim = None
            best = 0.0
            for cid, cvec in existing:
                s = cosine(vec, cvec)
                if s > best:
                    best, target_claim = s, cid
            if target_claim and best >= CANON_THRESHOLD:
                # ¿ya hay evidencia de este documento para esta afirmación?
                dup = conn.execute(
                    "SELECT 1 FROM claim_evidence WHERE claim_id = ? AND document_id = ?", (target_claim, doc["id"])
                ).fetchone()
                if dup:
                    continue
                conn.execute(
                    """INSERT INTO claim_evidence(id, claim_id, document_id, stance, quote, extracted_by, confidence, created_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (new_id(), target_claim, doc["id"], "supports", cand.quote, cand.extracted_by, round(best, 3), ts),
                )
                stats["merged"] += 1
                claim_id = target_claim
            else:
                claim_id = new_id()
                conn.execute(
                    """INSERT INTO claim(id, event_id, document_id, text_canonical, text_original, level, status,
                       check_worthy, attributed_to, extracted_by, first_seen_at, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (claim_id, event_id, doc["id"], cand.text, cand.text, cand.level, "unverified",
                     cand.check_worthy, cand.attributed_to, cand.extracted_by, doc.get("published_at") or ts, ts),
                )
                conn.execute(
                    """INSERT INTO claim_evidence(id, claim_id, document_id, stance, quote, extracted_by, confidence, created_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (new_id(), claim_id, doc["id"], "supports", cand.quote, cand.extracted_by, 1.0, ts),
                )
                existing.append((claim_id, vec))
                stats["new"] += 1
            # recalcular estado
            ev_rows = [
                dict(r)
                for r in conn.execute(
                    """SELECT ce.stance, ce.quote, d.source_id, s.tier FROM claim_evidence ce
                       JOIN document d ON d.id = ce.document_id JOIN source s ON s.id = d.source_id
                       WHERE ce.claim_id = ?""",
                    (claim_id,),
                ).fetchall()
            ]
            new_status = compute_status(ev_rows)
            old_status = conn.execute("SELECT status FROM claim WHERE id = ?", (claim_id,)).fetchone()["status"]
            if new_status != old_status:
                conn.execute("UPDATE claim SET status = ? WHERE id = ?", (new_status, claim_id))
                conn.execute(
                    """INSERT INTO claim_revision(id, claim_id, old_status, new_status, reason, evidence_ids, changed_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (new_id(), claim_id, old_status, new_status,
                     f"{len(ev_rows)} evidencias; regla determinista (primaria o ≥2 independientes tier≤2)",
                     dumps([]), ts),
                )
                stats["status_changes"] += 1
    return stats


def claims_for_event(db: Database, event_id: str, limit: int = 40) -> list[dict[str, Any]]:
    rows = db.all(
        """SELECT c.*, d.title AS doc_title, d.url AS doc_url, s.name AS source_name, s.tier AS source_tier
           FROM claim c JOIN document d ON d.id = c.document_id JOIN source s ON s.id = d.source_id
           WHERE c.event_id = ? ORDER BY c.check_worthy DESC, c.created_at ASC LIMIT ?""",
        (event_id, limit),
    )
    out = []
    for r in rows:
        d = dict(r)
        d["evidence"] = [
            dict(e)
            for e in db.all(
                """SELECT ce.id, ce.stance, ce.quote, ce.extracted_by, ce.confidence, ce.created_at, ce.document_id,
                          d.title AS doc_title, d.url AS doc_url, d.published_at, s.name AS source_name, s.tier AS source_tier,
                          s.ideology_label, s.region_bloc, s.id AS source_id
                   FROM claim_evidence ce JOIN document d ON d.id = ce.document_id JOIN source s ON s.id = d.source_id
                   WHERE ce.claim_id = ? ORDER BY d.published_at ASC""",
                (r["id"],),
            )
        ]
        d["revisions"] = [dict(x) for x in db.all("SELECT * FROM claim_revision WHERE claim_id = ? ORDER BY changed_at", (r["id"],))]
        for rev in d["revisions"]:
            rev["evidence_ids"] = loads(rev.get("evidence_ids"), [])
        out.append(d)
    return out


__all__ = [
    "ClaimCandidate",
    "heuristic_claims",
    "quote_supported",
    "persist_claims",
    "compute_status",
    "claims_for_event",
    "blob_to_vec",
    "vec_to_blob",
]
