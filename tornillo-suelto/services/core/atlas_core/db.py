"""Acceso a datos: SQLite (WAL + FTS5). Ver ADR-0001.

El esquema conserva los nombres del schema.sql de referencia (Postgres) para que una migración futura sea
mecánica. Los vectores se guardan como BLOB float32 y se buscan por fuerza bruta con NumPy.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from .settings import settings

SCHEMA_VERSION = 1

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS source (
  id TEXT PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL, domain TEXT,
  type TEXT NOT NULL, tier INTEGER NOT NULL, country TEXT, languages TEXT NOT NULL DEFAULT '[]',
  region_bloc TEXT, state_relation TEXT, ideology_label TEXT, paywall TEXT DEFAULT 'none',
  feeds TEXT NOT NULL DEFAULT '[]', feed_status TEXT DEFAULT 'unknown', active INTEGER DEFAULT 1,
  poll_minutes INTEGER DEFAULT 30, review_status TEXT DEFAULT 'seed_unverified', group_name TEXT,
  etag TEXT, last_modified TEXT, last_polled_at TEXT, last_ok_at TEXT, last_error TEXT, last_items INTEGER DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_health (
  id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT NOT NULL, checked_at TEXT NOT NULL,
  ok INTEGER, items INTEGER, error TEXT, latency_ms INTEGER
);
CREATE INDEX IF NOT EXISTS ix_source_health ON source_health(source_id, checked_at DESC);

CREATE TABLE IF NOT EXISTS document (
  id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES source(id), kind TEXT NOT NULL DEFAULT 'article',
  url TEXT NOT NULL UNIQUE, canonical_url TEXT, title TEXT, lede TEXT, text TEXT, lang TEXT, authors TEXT DEFAULT '[]',
  published_at TEXT, fetched_at TEXT NOT NULL, content_hash TEXT, extraction_method TEXT, paywalled INTEGER DEFAULT 0,
  embedding BLOB, embedding_model TEXT, countries TEXT DEFAULT '[]', event_id TEXT, meta TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_document_published ON document(published_at DESC);
CREATE INDEX IF NOT EXISTS ix_document_source ON document(source_id, published_at DESC);
CREATE INDEX IF NOT EXISTS ix_document_event ON document(event_id);
CREATE INDEX IF NOT EXISTS ix_document_hash ON document(content_hash);
CREATE VIRTUAL TABLE IF NOT EXISTS document_fts USING fts5(doc_id UNINDEXED, title, lede, text, tokenize='unicode61 remove_diacritics 2');

CREATE TABLE IF NOT EXISTS entity (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL, aliases TEXT DEFAULT '[]', wikidata_qid TEXT,
  country TEXT, description TEXT, attributes TEXT DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_entity_kind ON entity(kind);
CREATE TABLE IF NOT EXISTS document_entity (
  document_id TEXT NOT NULL, entity_id TEXT NOT NULL, salience REAL, PRIMARY KEY (document_id, entity_id)
);
CREATE INDEX IF NOT EXISTS ix_docent_entity ON document_entity(entity_id);

CREATE TABLE IF NOT EXISTS event (
  id TEXT PRIMARY KEY, title_neutral TEXT NOT NULL, title_source TEXT DEFAULT 'lead_document', summary TEXT,
  domain TEXT, countries TEXT DEFAULT '[]', geo TEXT, first_seen_at TEXT, last_update_at TEXT,
  status TEXT DEFAULT 'developing', merged_into TEXT, materiality REAL DEFAULT 0, materiality_breakdown TEXT,
  coverage_stats TEXT, silence_index TEXT, centroid BLOB, embedding_model TEXT, n_docs INTEGER DEFAULT 0,
  parent_event_id TEXT, lead_document_id TEXT, entity_keys TEXT DEFAULT '[]', user_flag TEXT
);
CREATE INDEX IF NOT EXISTS ix_event_update ON event(last_update_at DESC);
CREATE INDEX IF NOT EXISTS ix_event_materiality ON event(materiality DESC);
CREATE TABLE IF NOT EXISTS event_document (
  event_id TEXT NOT NULL, document_id TEXT NOT NULL, similarity REAL, PRIMARY KEY (event_id, document_id)
);

CREATE TABLE IF NOT EXISTS claim (
  id TEXT PRIMARY KEY, event_id TEXT, document_id TEXT NOT NULL, text_canonical TEXT NOT NULL, text_original TEXT,
  level TEXT NOT NULL DEFAULT 'fact', status TEXT NOT NULL DEFAULT 'unverified', check_worthy REAL DEFAULT 0.5,
  attributed_to TEXT, extracted_by TEXT NOT NULL, first_seen_at TEXT, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_claim_event ON claim(event_id);
CREATE TABLE IF NOT EXISTS claim_evidence (
  id TEXT PRIMARY KEY, claim_id TEXT NOT NULL, document_id TEXT NOT NULL, stance TEXT NOT NULL, quote TEXT NOT NULL,
  extracted_by TEXT, confidence REAL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_evidence_claim ON claim_evidence(claim_id);
CREATE TABLE IF NOT EXISTS claim_revision (
  id TEXT PRIMARY KEY, claim_id TEXT NOT NULL, old_status TEXT, new_status TEXT, reason TEXT,
  evidence_ids TEXT DEFAULT '[]', changed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS frame (
  id TEXT PRIMARY KEY, event_id TEXT NOT NULL, label TEXT, problem TEXT, cause TEXT, moral_judgment TEXT, remedy TEXT,
  evidence_offered TEXT, marker_terms TEXT DEFAULT '[]', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS document_frame (
  document_id TEXT NOT NULL, frame_id TEXT NOT NULL, strength REAL, stance REAL, PRIMARY KEY (document_id, frame_id)
);

CREATE TABLE IF NOT EXISTS state_variable (
  id TEXT PRIMARY KEY, scope TEXT NOT NULL, dimension TEXT NOT NULL, key TEXT NOT NULL, unit TEXT, source_hint TEXT,
  threshold TEXT, UNIQUE (scope, key)
);
CREATE TABLE IF NOT EXISTS state_observation (
  variable_id TEXT NOT NULL, observed_at TEXT NOT NULL, value_num REAL, value_text TEXT, source_doc_id TEXT,
  source_note TEXT, PRIMARY KEY (variable_id, observed_at)
);
CREATE TABLE IF NOT EXISTS state_delta (
  id TEXT PRIMARY KEY, variable_id TEXT NOT NULL, event_id TEXT, detected_at TEXT NOT NULL, magnitude REAL,
  description TEXT, source_doc_id TEXT
);

CREATE TABLE IF NOT EXISTS forecast_question (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, resolution_criteria TEXT NOT NULL, resolution_source TEXT,
  kind TEXT DEFAULT 'binary', options TEXT, open_at TEXT NOT NULL, close_at TEXT NOT NULL, resolve_by TEXT,
  resolved_at TEXT, outcome TEXT, origin_event_id TEXT, domain TEXT, countries TEXT DEFAULT '[]',
  base_rate REAL, base_rate_note TEXT, market_links TEXT DEFAULT '[]', status TEXT DEFAULT 'open', created_by TEXT
);
CREATE TABLE IF NOT EXISTS forecast (
  id TEXT PRIMARY KEY, question_id TEXT NOT NULL, forecaster TEXT NOT NULL, probability REAL, distribution TEXT,
  rationale TEXT, evidence_ids TEXT DEFAULT '[]', made_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_forecast_q ON forecast(question_id, made_at);
CREATE TABLE IF NOT EXISTS forecast_score (
  question_id TEXT NOT NULL, forecaster TEXT NOT NULL, brier REAL, log_score REAL, PRIMARY KEY (question_id, forecaster)
);

CREATE TABLE IF NOT EXISTS prediction_market (
  id TEXT PRIMARY KEY, venue TEXT NOT NULL, market_id TEXT NOT NULL, question TEXT NOT NULL, probability REAL,
  volume REAL, liquidity REAL, url TEXT, close_at TEXT, fetched_at TEXT NOT NULL, tags TEXT DEFAULT '[]', followed INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS market_quote (
  symbol TEXT PRIMARY KEY, label TEXT, group_name TEXT, price REAL, change_pct REAL, currency TEXT,
  observed_at TEXT, fetched_at TEXT, source TEXT, history TEXT DEFAULT '[]', error TEXT
);

CREATE TABLE IF NOT EXISTS argument_map (id TEXT PRIMARY KEY, title TEXT NOT NULL, topic TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS argument_node (
  id TEXT PRIMARY KEY, map_id TEXT NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL, author TEXT, work TEXT,
  is_user INTEGER DEFAULT 0, x REAL, y REAL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS argument_edge (
  id TEXT PRIMARY KEY, map_id TEXT NOT NULL, src TEXT NOT NULL, dst TEXT NOT NULL, rel TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS historical_case (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT, start_date TEXT, end_date TEXT, countries TEXT DEFAULT '[]',
  variables TEXT DEFAULT '{}', outcome TEXT, duration_months REAL, summary TEXT, sources TEXT DEFAULT '[]',
  embedding BLOB, embedding_model TEXT
);

CREATE TABLE IF NOT EXISTS note (
  id TEXT PRIMARY KEY, title TEXT, body_text TEXT NOT NULL DEFAULT '', links TEXT DEFAULT '[]', course TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS review_card (
  id TEXT PRIMARY KEY, front TEXT NOT NULL, back TEXT NOT NULL, source_ref TEXT DEFAULT '{}', fsrs_state TEXT DEFAULT '{}',
  due_at TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reading_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, document_id TEXT, event_id TEXT, source_id TEXT, action TEXT NOT NULL,
  seconds INTEGER DEFAULT 0, at TEXT NOT NULL, topic TEXT
);

CREATE TABLE IF NOT EXISTS business_unit (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, sectors TEXT DEFAULT '[]', jurisdictions TEXT DEFAULT '[]',
  markets TEXT DEFAULT '[]', currencies TEXT DEFAULT '[]', regulations TEXT DEFAULT '[]', keywords TEXT DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS exposure_alert (
  id TEXT PRIMARY KEY, business_id TEXT NOT NULL, event_id TEXT NOT NULL, channel TEXT NOT NULL, explanation TEXT,
  confidence REAL, created_at TEXT NOT NULL, dismissed INTEGER DEFAULT 0, UNIQUE (business_id, event_id, channel)
);
CREATE TABLE IF NOT EXISTS decision_log (
  id TEXT PRIMARY KEY, business_id TEXT, title TEXT NOT NULL, context TEXT, premises TEXT DEFAULT '[]',
  alternatives TEXT DEFAULT '[]', success_probability REAL, premortem TEXT, decided_at TEXT NOT NULL, review_at TEXT,
  outcome TEXT, lessons TEXT
);

CREATE TABLE IF NOT EXISTS brief (
  id TEXT PRIMARY KEY, date TEXT NOT NULL, kind TEXT NOT NULL, composed_by TEXT NOT NULL, content TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_brief_date ON brief(date DESC, kind);

CREATE TABLE IF NOT EXISTS llm_call (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, module TEXT, agent TEXT, prompt_name TEXT, prompt_version TEXT,
  model TEXT, input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER, cache_write_tokens INTEGER,
  cost_usd REAL, latency_ms INTEGER, ok INTEGER, error TEXT, meta TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS job_run (
  id INTEGER PRIMARY KEY AUTOINCREMENT, job TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT, ok INTEGER,
  stats TEXT DEFAULT '{}', error TEXT
);
CREATE TABLE IF NOT EXISTS agent_run (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, ref TEXT, status TEXT NOT NULL, output TEXT, created_at TEXT NOT NULL,
  finished_at TEXT, cost_usd REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS alert (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT, ref TEXT DEFAULT '{}', created_at TEXT NOT NULL,
  read INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS setting (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def loads(s: str | None, default: Any = None) -> Any:
    if s is None or s == "":
        return default
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return default


def vec_to_blob(v: np.ndarray | None) -> bytes | None:
    if v is None:
        return None
    return np.asarray(v, dtype=np.float32).tobytes()


def blob_to_vec(b: bytes | None) -> np.ndarray | None:
    if b is None:
        return None
    return np.frombuffer(b, dtype=np.float32)


class Database:
    """Conexión SQLite compartida por hilo. `with db.tx() as cur:` para escribir."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else settings.db_path
        self._local = threading.local()
        self._init_lock = threading.Lock()
        self._initialized = False

    def _connect(self) -> sqlite3.Connection:
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path), timeout=30, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    @property
    def conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._connect()
            self._local.conn = conn
        if not self._initialized:
            with self._init_lock:
                if not self._initialized:
                    conn.executescript(SCHEMA)
                    conn.execute(
                        "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
                        (str(SCHEMA_VERSION),),
                    )
                    self._initialized = True
        return conn

    @contextmanager
    def tx(self):
        conn = self.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    # ---- helpers de lectura ----
    def one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, tuple(params)).fetchone()

    def all(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, tuple(params)).fetchall()

    def scalar(self, sql: str, params: Iterable[Any] = (), default: Any = None) -> Any:
        row = self.one(sql, params)
        if row is None:
            return default
        return row[0]

    def exec(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, tuple(params))

    def insert(self, table: str, row: dict[str, Any], replace: bool = False) -> None:
        cols = ", ".join(row.keys())
        marks = ", ".join("?" for _ in row)
        verb = "INSERT OR REPLACE" if replace else "INSERT"
        self.conn.execute(f"{verb} INTO {table} ({cols}) VALUES ({marks})", tuple(row.values()))

    def update(self, table: str, row_id: str, fields: dict[str, Any], id_col: str = "id") -> None:
        if not fields:
            return
        sets = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(f"UPDATE {table} SET {sets} WHERE {id_col} = ?", (*fields.values(), row_id))

    def get_setting(self, key: str, default: Any = None) -> Any:
        row = self.one("SELECT value FROM setting WHERE key = ?", (key,))
        return loads(row["value"]) if row else default

    def set_setting(self, key: str, value: Any) -> None:
        self.conn.execute("INSERT OR REPLACE INTO setting(key, value) VALUES (?, ?)", (key, dumps(value)))

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None


_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


def set_db(db: Database) -> None:
    """Para tests: sustituir la base de datos global."""
    global _db
    _db = db


def row_to_dict(row: sqlite3.Row | None, json_fields: Iterable[str] = ()) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    for f in json_fields:
        if f in d:
            d[f] = loads(d[f], default=[] if f.endswith("s") or f in ("links", "feeds") else {})
    d.pop("embedding", None)
    d.pop("centroid", None)
    return d
