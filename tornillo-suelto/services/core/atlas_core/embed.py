"""Embeddings locales por niveles (ADR-0003).

- HashingEmbedder (por defecto): n-gramas de caracteres y palabras, hashing a 1024 dims, L2. Sin descargas.
- SentenceTransformerEmbedder: bge-m3 si está instalado y ATLAS_EMBEDDINGS=bge-m3.
Ambos producen vectores float32 de dimensión DIM. Los espacios no se mezclan: cada fila guarda `embedding_model`.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from functools import lru_cache

import numpy as np

from .settings import settings

DIM = 1024

_STOP = set(
    """
    de la que el en y a los del se las por un para con no una su al lo como más pero sus le ya o este sí porque
    esta entre cuando muy sin sobre también me hasta hay donde quien desde todo nos durante todos uno les ni contra
    otros ese eso ante ellos e esto mí antes algunos qué unos yo otro otras otra él tanto esa estos mucho quienes
    nada muchos cual poco ella estar estas algunas algo nosotros
    the of and to in a is that for on with as by at from it an be this are was or has have not its but their
    were which will after new said also more over than into about who up out one two first last
    le les des du et un une en dans pour que qui sur au aux pas plus par avec ce se ne son sa ses
    der die das und in den von zu mit ist für auf dem des sich nicht ein eine als auch es an werden aus er hat
    di il la le e che un una per in con del della non sono da si al lo dei delle
    """.split()
)

_word_re = re.compile(r"[\w'-]+", re.UNICODE)
_MONTHS = set(
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre january february march april may june july august september october november december janvier fevrier mars avril mai juin juillet aout octobre novembre decembre januar februar marz mai juni juli oktober dezember lunes martes miercoles jueves viernes sabado domingo monday tuesday wednesday thursday friday saturday sunday".split()
)


def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()


def tokens(s: str) -> list[str]:
    return [t for t in _word_re.findall(normalize_text(s)) if t not in _STOP and len(t) > 1]


def content_tokens(s: str) -> list[str]:
    """Tokens para embeddings: sin cifras sueltas, fechas ni días/meses (boilerplate de boletines y agencias)."""
    out = []
    for t in tokens(s):
        if t.isdigit() or t in _MONTHS or re.fullmatch(r"\d+[a-z]{0,3}", t):
            continue
        out.append(t)
    return out


class IDF:
    """Pesos IDF calculados sobre el corpus local (títulos y entradillas). Tokens no vistos → peso máximo."""

    def __init__(self, doc_freq: dict[str, int] | None = None, n_docs: int = 0):
        self.df = doc_freq or {}
        self.n = max(1, n_docs)
        self.max_idf = math.log((self.n + 1) / 1.0) + 1.0

    def weight(self, token: str) -> float:
        df = self.df.get(token)
        if df is None:
            return self.max_idf
        return math.log((self.n + 1) / (df + 1)) + 1.0

    @classmethod
    def from_texts(cls, texts: list[str]) -> IDF:
        df: dict[str, int] = {}
        for t in texts:
            for tok in set(content_tokens(t)):
                df[tok] = df.get(tok, 0) + 1
        return cls(df, len(texts))


_idf: IDF = IDF()


def set_idf(idf: IDF) -> None:
    global _idf
    _idf = idf


def get_idf() -> IDF:
    return _idf


def _h(feature: str) -> tuple[int, float]:
    d = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
    idx = int.from_bytes(d[:4], "little") % DIM
    sign = 1.0 if d[4] & 1 else -1.0
    return idx, sign


class HashingEmbedder:
    """Hashing trick sobre palabras (ponderadas por IDF), bigramas y n-gramas de caracteres, más tokens de
    entidad del gazetteer (independientes del idioma) cuando se pasan en `extra_tokens`."""

    name = "hashing-v2"

    def embed(self, text: str, extra_tokens: list[str] | None = None) -> np.ndarray:
        vec = np.zeros(DIM, dtype=np.float32)
        toks = content_tokens(text)
        idf = get_idf()
        if not toks and not extra_tokens:
            return vec
        for t in toks:
            w = idf.weight(t)
            i, s = _h("w:" + t)
            vec[i] += 2.0 * w * s
            if len(t) >= 5:
                padded = f"#{t}#"
                for n in (4, 5):
                    for k in range(len(padded) - n + 1):
                        i, s = _h(f"c{n}:" + padded[k : k + n])
                        vec[i] += 0.35 * w * s
        for a, b in zip(toks, toks[1:], strict=False):
            i, s = _h(f"b:{a}_{b}")
            vec[i] += 1.0 * min(idf.weight(a), idf.weight(b)) * s
        for e in extra_tokens or []:
            i, s = _h("e:" + e)
            vec[i] += 4.0 * s
        vec = np.sign(vec) * np.log1p(np.abs(vec))
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec.astype(np.float32)

    def embed_many(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, DIM), dtype=np.float32)
        return np.stack([self.embed(t) for t in texts])


class SentenceTransformerEmbedder:
    name = "bge-m3"

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer  # type: ignore

        self.model = SentenceTransformer("BAAI/bge-m3")

    def embed(self, text: str, extra_tokens: list[str] | None = None) -> np.ndarray:
        v = self.model.encode([text], normalize_embeddings=True)[0]
        return np.asarray(v, dtype=np.float32)

    def embed_many(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, DIM), dtype=np.float32)
        return np.asarray(self.model.encode(texts, normalize_embeddings=True), dtype=np.float32)


@lru_cache(maxsize=1)
def get_embedder():
    if settings.atlas_embeddings == "bge-m3":
        try:
            return SentenceTransformerEmbedder()
        except Exception:  # noqa: BLE001 - degradación explícita
            return HashingEmbedder()
    return HashingEmbedder()


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def cosine_matrix(q: np.ndarray, m: np.ndarray) -> np.ndarray:
    """Similitud coseno entre un vector q y una matriz m (filas ya normalizadas o no)."""
    if m.size == 0:
        return np.zeros(0, dtype=np.float32)
    qn = q / (np.linalg.norm(q) or 1.0)
    mn = m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-9)
    return mn @ qn
