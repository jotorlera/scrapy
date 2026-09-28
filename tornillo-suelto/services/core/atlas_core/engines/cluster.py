"""Clustering incremental de documentos en eventos (docs/spec/07 §1).

Regla: un documento se une al evento activo más cercano si (a) la similitud coseno con su centroide supera θ,
(b) comparte al menos una entidad principal (país, institución o empresa del gazetteer) y (c) la fecha es
coherente (ventana de 72 h respecto de la última actualización del evento). Si no, crea un evento candidato.
θ depende del embedder: 0,42 para el hashing (n-gramas) y 0,78 para bge-m3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import numpy as np

from ..db import Database, blob_to_vec, dumps, loads, new_id, now_iso, vec_to_blob
from ..embed import DIM, get_embedder
from ..gazetteer import countries
from ..util import parse_iso

THETA_BY_MODEL = {"hashing-v1": 0.42, "hashing-v2": 0.40, "bge-m3": 0.78}
# Un evento formado solo por documentos de UNA fuente exige mucha más similitud para aceptar otro de la misma
# fuente: evita que el boilerplate de boletines y agencias (mismas fórmulas, distinto asunto) se aglutine.
SAME_SOURCE_EXTRA = 0.25
ACTIVE_WINDOW_DAYS = 7
TIME_COHERENCE_HOURS = 72


@dataclass
class EventState:
    id: str
    centroid: np.ndarray
    n_docs: int
    entity_keys: set[str]
    countries: list[str]
    last_update_at: str
    domain: str
    dirty: bool = False
    new: bool = False
    title: str = ""
    lead_document_id: str | None = None
    first_seen_at: str | None = None
    topics: list[str] = field(default_factory=list)
    sources: set[str] = field(default_factory=set)


class ClusterIndex:
    """Índice en memoria de los eventos activos. Se carga una vez por pasada de ingesta y se vuelca al final."""

    def __init__(self, db: Database, theta: float | None = None):
        self.db = db
        self.model = get_embedder().name
        self.theta = theta if theta is not None else THETA_BY_MODEL.get(self.model, 0.5)
        self.events: dict[str, EventState] = {}
        self._matrix: np.ndarray | None = None
        self._ids: list[str] = []
        self._load()

    def _load(self) -> None:
        since = (parse_iso(now_iso()) - timedelta(days=ACTIVE_WINDOW_DAYS)).isoformat()  # type: ignore[operator]
        rows = self.db.all(
            """SELECT id, centroid, n_docs, entity_keys, countries, last_update_at, domain, title_neutral,
                      lead_document_id, first_seen_at
               FROM event WHERE status != 'merged' AND last_update_at >= ? AND embedding_model = ?""",
            (since, self.model),
        )
        src_rows = self.db.all(
            """SELECT d.event_id, d.source_id FROM document d JOIN event e ON e.id = d.event_id
               WHERE e.status != 'merged' AND e.last_update_at >= ? GROUP BY d.event_id, d.source_id""",
            (since,),
        )
        sources_by_event: dict[str, set[str]] = {}
        for r in src_rows:
            sources_by_event.setdefault(r["event_id"], set()).add(r["source_id"])
        for r in rows:
            vec = blob_to_vec(r["centroid"])
            if vec is None or vec.shape[0] != DIM:
                continue
            self.events[r["id"]] = EventState(
                sources=sources_by_event.get(r["id"], set()),
                id=r["id"],
                centroid=vec.copy(),
                n_docs=r["n_docs"] or 1,
                entity_keys=set(loads(r["entity_keys"], [])),
                countries=loads(r["countries"], []),
                last_update_at=r["last_update_at"],
                domain=r["domain"] or "politics",
                title=r["title_neutral"],
                lead_document_id=r["lead_document_id"],
                first_seen_at=r["first_seen_at"],
            )
        self._rebuild()

    def _rebuild(self) -> None:
        self._ids = list(self.events.keys())
        if self._ids:
            self._matrix = np.stack([self.events[i].centroid for i in self._ids])
        else:
            self._matrix = np.zeros((0, DIM), dtype=np.float32)

    def assign(
        self,
        doc_id: str,
        vec: np.ndarray,
        entity_keys: list[str],
        country_codes: list[str],
        published_at: str | None,
        domain: str,
        title: str,
        topics: list[str],
        source_id: str | None = None,
    ) -> tuple[str, float, bool]:
        """Devuelve (event_id, similitud, creado_nuevo)."""
        keys = set(entity_keys)
        ts = parse_iso(published_at) or parse_iso(now_iso())
        best_id, best_sim = None, 0.0
        if self._matrix is not None and self._matrix.shape[0] > 0:
            norms = np.linalg.norm(self._matrix, axis=1) + 1e-9
            sims = (self._matrix @ vec) / (norms * (np.linalg.norm(vec) + 1e-9))
            order = np.argsort(-sims)[:15]
            for idx in order:
                sim = float(sims[idx])
                if sim < self.theta:
                    break
                ev = self.events[self._ids[idx]]
                same_source_only = bool(source_id) and ev.sources == {source_id}
                if same_source_only and sim < self.theta + SAME_SOURCE_EXTRA:
                    continue
                if keys and ev.entity_keys and not (keys & ev.entity_keys):
                    continue
                if not keys and ev.entity_keys and sim < self.theta + 0.15:
                    continue
                last = parse_iso(ev.last_update_at)
                if last and ts and abs((ts - last).total_seconds()) > TIME_COHERENCE_HOURS * 3600:
                    continue
                best_id, best_sim = ev.id, sim
                break
        if best_id is not None:
            ev = self.events[best_id]
            n = ev.n_docs
            ev.centroid = (ev.centroid * n + vec) / (n + 1)
            ev.n_docs = n + 1
            if source_id:
                ev.sources.add(source_id)
            ev.entity_keys |= keys
            if len(ev.entity_keys) > 12:
                ev.entity_keys = set(list(ev.entity_keys)[:12])
            for c in country_codes:
                if c not in ev.countries:
                    ev.countries.append(c)
            if ts and (parse_iso(ev.last_update_at) or ts) < ts:
                ev.last_update_at = ts.isoformat()
            # el lote se procesa del más reciente al más antiguo: el primer documento visto no es el primero publicado
            if ts and (parse_iso(ev.first_seen_at) or ts) > ts:
                ev.first_seen_at = ts.isoformat()
            for t in topics:
                if t not in ev.topics:
                    ev.topics.append(t)
            ev.dirty = True
            # refrescar fila de la matriz
            i = self._ids.index(best_id)
            self._matrix[i] = ev.centroid  # type: ignore[index]
            return best_id, best_sim, False
        # nuevo evento
        eid = new_id()
        when = (ts or parse_iso(now_iso())).isoformat()  # type: ignore[union-attr]
        ev = EventState(
            id=eid,
            centroid=vec.copy(),
            n_docs=1,
            entity_keys=keys,
            countries=list(country_codes),
            last_update_at=when,
            domain=domain,
            dirty=True,
            new=True,
            title=title,
            lead_document_id=doc_id,
            first_seen_at=when,
            topics=list(topics),
            sources={source_id} if source_id else set(),
        )
        self.events[eid] = ev
        self._ids.append(eid)
        self._matrix = (
            np.vstack([self._matrix, vec[None, :]])
            if self._matrix is not None and self._matrix.size
            else vec[None, :].copy()
        )
        return eid, 1.0, True

    def flush(self) -> tuple[int, int]:
        """Escribe eventos nuevos y modificados. Devuelve (nuevos, actualizados)."""
        created, updated = 0, 0
        cmap = countries()
        with self.db.tx() as conn:
            for ev in self.events.values():
                if not ev.dirty:
                    continue
                geo = None
                for c in ev.countries:
                    if c in cmap:
                        geo = {"lat": cmap[c].lat, "lon": cmap[c].lon}
                        break
                if ev.new:
                    conn.execute(
                        """INSERT INTO event(id, title_neutral, title_source, domain, countries, geo, first_seen_at,
                           last_update_at, status, centroid, embedding_model, n_docs, lead_document_id, entity_keys,
                           coverage_stats)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            ev.id,
                            ev.title,
                            "lead_document",
                            ev.domain,
                            dumps(ev.countries),
                            dumps(geo),
                            ev.first_seen_at,
                            ev.last_update_at,
                            "developing",
                            vec_to_blob(ev.centroid),
                            self.model,
                            ev.n_docs,
                            ev.lead_document_id,
                            dumps(sorted(ev.entity_keys)),
                            dumps({"topics": ev.topics}),
                        ),
                    )
                    created += 1
                else:
                    conn.execute(
                        """UPDATE event SET centroid=?, n_docs=?, entity_keys=?, countries=?, geo=COALESCE(geo, ?),
                           first_seen_at=COALESCE(?, first_seen_at), last_update_at=? WHERE id=?""",
                        (
                            vec_to_blob(ev.centroid),
                            ev.n_docs,
                            dumps(sorted(ev.entity_keys)),
                            dumps(ev.countries),
                            dumps(geo),
                            ev.first_seen_at,
                            ev.last_update_at,
                            ev.id,
                        ),
                    )
                    updated += 1
                ev.dirty = False
                ev.new = False
        return created, updated


MERGE_THETA_EXTRA = 0.08


def _earliest(*stamps: str | None) -> str | None:
    """La más antigua de varias fechas ISO (ignora None e ilegibles); devuelve la cadena original."""
    parsed = [(parse_iso(s), s) for s in stamps if s]
    parsed = [(d, s) for d, s in parsed if d]
    return min(parsed)[1] if parsed else None


def _latest(*stamps: str | None) -> str | None:
    parsed = [(parse_iso(s), s) for s in stamps if s]
    parsed = [(d, s) for d, s in parsed if d]
    return max(parsed)[1] if parsed else None


def consolidate_events(db: Database, hours: int = 48) -> dict[str, int]:
    """Reconsolidación periódica (docs/spec/07 §1): fusiona eventos activos cuyos centroides sean muy similares,
    compartan entidad principal y sean coherentes en el tiempo. El evento con más documentos absorbe al otro;
    el absorbido queda `status='merged'` con `merged_into` (nunca se borra historia)."""
    model = get_embedder().name
    theta = THETA_BY_MODEL.get(model, 0.5) + MERGE_THETA_EXTRA
    rows = db.all(
        """SELECT id, centroid, n_docs, entity_keys, last_update_at, first_seen_at, countries FROM event
           WHERE status != 'merged' AND embedding_model = ? AND last_update_at >= datetime('now', ?) ORDER BY n_docs DESC""",
        (model, f"-{hours} hours"),
    )
    evs = []
    for r in rows:
        v = blob_to_vec(r["centroid"])
        if v is None:
            continue
        evs.append(
            (
                r["id"],
                v / (np.linalg.norm(v) + 1e-9),
                set(loads(r["entity_keys"], [])),
                r["n_docs"],
                parse_iso(r["last_update_at"]),
                loads(r["countries"], []),
            )
        )
    if len(evs) < 2:
        return {"merged": 0, "checked": len(evs)}
    M = np.stack([e[1] for e in evs])
    S = M @ M.T
    np.fill_diagonal(S, -1.0)
    absorbed: set[str] = set()
    merges: list[tuple[str, str]] = []  # (loser, winner)
    for i in range(len(evs)):
        if evs[i][0] in absorbed:
            continue
        for j in np.argsort(-S[i])[:5]:
            j = int(j)
            if S[i, j] < theta or evs[j][0] in absorbed or j <= i:
                continue
            ki, kj = evs[i][2], evs[j][2]
            if ki and kj and not (ki & kj):
                continue
            ti, tj = evs[i][4], evs[j][4]
            if ti and tj and abs((ti - tj).total_seconds()) > TIME_COHERENCE_HOURS * 3600:
                continue
            absorbed.add(evs[j][0])
            merges.append((evs[j][0], evs[i][0]))
    cmap = countries()
    with db.tx() as conn:
        for loser, winner in merges:
            conn.execute("UPDATE document SET event_id = ? WHERE event_id = ?", (winner, loser))
            conn.execute(
                "UPDATE OR IGNORE event_document SET event_id = ? WHERE event_id = ?", (winner, loser)
            )
            conn.execute("DELETE FROM event_document WHERE event_id = ?", (loser,))
            conn.execute("UPDATE claim SET event_id = ? WHERE event_id = ?", (winner, loser))
            conn.execute("UPDATE state_delta SET event_id = ? WHERE event_id = ?", (winner, loser))
            conn.execute(
                "UPDATE OR IGNORE exposure_alert SET event_id = ? WHERE event_id = ?", (winner, loser)
            )
            conn.execute("DELETE FROM exposure_alert WHERE event_id = ?", (loser,))
            conn.execute(
                "UPDATE forecast_question SET origin_event_id = ? WHERE origin_event_id = ?", (winner, loser)
            )
            conn.execute("UPDATE event SET status = 'merged', merged_into = ? WHERE id = ?", (winner, loser))
            # recomputar centroide, n_docs, países y claves del ganador a partir de sus documentos
            docs = conn.execute(
                "SELECT embedding, countries FROM document WHERE event_id = ? AND embedding IS NOT NULL",
                (winner,),
            ).fetchall()
            vecs = [blob_to_vec(d["embedding"]) for d in docs if d["embedding"]]
            countries_all: list[str] = []
            for d in docs:
                for c in loads(d["countries"], []):
                    if c not in countries_all:
                        countries_all.append(c)
            w_row = conn.execute(
                "SELECT entity_keys, first_seen_at, last_update_at FROM event WHERE id = ?", (winner,)
            ).fetchone()
            l_row = conn.execute(
                "SELECT entity_keys, first_seen_at, last_update_at FROM event WHERE id = ?", (loser,)
            ).fetchone()
            w_keys = set(loads(w_row["entity_keys"], []))
            l_keys = set(loads(l_row["entity_keys"], []))
            geo = None
            for c in countries_all:
                if c in cmap:
                    geo = {"lat": cmap[c].lat, "lon": cmap[c].lon}
                    break
            if vecs:
                centroid = np.mean(np.stack(vecs), axis=0).astype(np.float32)
                # fechas desde los documentos (como el centroide): el ganador adopta el primer publicado y el
                # último; en Python porque MIN/MAX escalares de SQLite devuelven NULL si algún argumento es NULL
                span = conn.execute(
                    "SELECT MIN(published_at) AS lo, MAX(published_at) AS hi FROM document WHERE event_id = ?",
                    (winner,),
                ).fetchone()
                first_seen = _earliest(w_row["first_seen_at"], l_row["first_seen_at"], span["lo"])
                last_update = _latest(w_row["last_update_at"], l_row["last_update_at"], span["hi"])
                conn.execute(
                    """UPDATE event SET centroid = ?, n_docs = ?, countries = ?, entity_keys = ?, geo = COALESCE(geo, ?),
                       first_seen_at = COALESCE(?, first_seen_at), last_update_at = COALESCE(?, last_update_at)
                       WHERE id = ?""",
                    (
                        vec_to_blob(centroid),
                        len(docs),
                        dumps(countries_all[:6]),
                        dumps(sorted(w_keys | l_keys)[:12]),
                        dumps(geo),
                        first_seen,
                        last_update,
                        winner,
                    ),
                )
    return {"merged": len(merges), "checked": len(evs), "winners": sorted({w for _, w in merges})}  # type: ignore[dict-item]


def purity_and_fragmentation(assignments: list[tuple[str, str]]) -> dict[str, float]:
    """Métricas del conjunto dorado: pares (evento_predicho, evento_real)."""
    if not assignments:
        return {"purity": 0.0, "fragmentation": 0.0}
    by_pred: dict[str, dict[str, int]] = {}
    truth_sets: dict[str, set[str]] = {}
    for pred, truth in assignments:
        by_pred.setdefault(pred, {}).setdefault(truth, 0)
        by_pred[pred][truth] += 1
        truth_sets.setdefault(truth, set()).add(pred)
    majority = sum(max(d.values()) for d in by_pred.values())
    purity = majority / len(assignments)
    fragmentation = sum(len(s) for s in truth_sets.values()) / max(1, len(truth_sets))
    return {"purity": round(purity, 4), "fragmentation": round(fragmentation, 4)}


def event_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    for f in ("countries", "entity_keys", "materiality_breakdown", "coverage_stats", "silence_index", "geo"):
        if f in d:
            d[f] = loads(d[f], [] if f in ("countries", "entity_keys") else None)
    d.pop("centroid", None)
    return d
