-- ATLAS — Esquema inicial PostgreSQL 16 (+ pgvector, pg_trgm)
-- Punto de partida. Claude Code debe convertirlo en migraciones Alembic y puede mejorarlo (ADR).

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ───────────────────────── FUENTES ─────────────────────────
CREATE TABLE source (
  id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  slug             TEXT UNIQUE NOT NULL,
  name             TEXT NOT NULL,
  domain           TEXT,
  type             TEXT NOT NULL,          -- wire|newspaper|broadcaster|digital_native|magazine|state_media|think_tank|institution|central_bank|court|statistical_office|intl_org|academic|newsletter|podcast|social_account|data_api
  tier             SMALLINT NOT NULL CHECK (tier BETWEEN 1 AND 4),
  country          CHAR(2),
  languages        TEXT[] NOT NULL DEFAULT '{}',
  region_bloc      TEXT,
  state_relation   TEXT,                   -- independent|public_service_independent|state_aligned|state_controlled
  owner_entity_id  UUID,
  ideology         JSONB,                  -- {econ, social, authority, nation, establishment, foreign_policy} en [-1,1]
  ideology_label   TEXT,                   -- etiqueta global
  ideology_label_local TEXT,               -- etiqueta relativa al país
  ideology_confidence REAL,
  ideology_provenance JSONB,               -- [{rater, label, url, date}]
  factual_record   TEXT,
  corrections_policy TEXT,
  paywall          TEXT,
  access           TEXT[],                 -- rss|sitemap|api|scrape_allowed|metadata_only
  feeds            TEXT[],
  ai_optout        BOOLEAN DEFAULT FALSE,
  review_status    TEXT DEFAULT 'seed_unverified',
  active           BOOLEAN DEFAULT TRUE,
  poll_minutes     INT DEFAULT 30,
  created_at       TIMESTAMPTZ DEFAULT now(),
  updated_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE source_health (
  source_id    UUID REFERENCES source(id),
  checked_at   TIMESTAMPTZ DEFAULT now(),
  ok           BOOLEAN,
  items        INT,
  error        TEXT,
  latency_ms   INT
);

-- ───────────────────────── DOCUMENTOS ─────────────────────────
CREATE TABLE document (
  id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  source_id      UUID REFERENCES source(id),
  kind           TEXT NOT NULL,            -- article|official_doc|statement|speech|transcript|post|paper|dataset_release|vote_record|court_ruling
  url            TEXT NOT NULL,
  canonical_url  TEXT,
  title          TEXT,
  lede           TEXT,
  text           TEXT,
  lang           TEXT,
  authors        TEXT[],
  published_at   TIMESTAMPTZ,
  fetched_at     TIMESTAMPTZ DEFAULT now(),
  content_hash   TEXT,
  simhash        BIGINT,
  extraction_method TEXT,
  paywalled      BOOLEAN DEFAULT FALSE,
  translation_es TEXT,
  embedding      vector(1024),             -- bge-m3
  meta           JSONB DEFAULT '{}',
  tsv            tsvector,
  UNIQUE (canonical_url)
);
CREATE INDEX ON document USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON document USING gin (tsv);
CREATE INDEX ON document (published_at DESC);
CREATE INDEX ON document (source_id, published_at DESC);

-- versiones de un documento oficial (para DIFF)
CREATE TABLE document_version (
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lineage_key  TEXT NOT NULL,              -- p.ej. "ecb-monetary-policy-statement" o id del procedimiento legislativo
  document_id  UUID REFERENCES document(id),
  version_label TEXT,
  previous_id  UUID REFERENCES document_version(id),
  diff_summary JSONB,                      -- cambios materiales resumidos
  created_at   TIMESTAMPTZ DEFAULT now()
);

-- ───────────────────────── ENTIDADES Y GRAFO ─────────────────────────
CREATE TABLE entity (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  kind          TEXT NOT NULL,             -- person|organization|country|institution|party|media_outlet|asset|sector|concept|work|treaty|conflict|place|company_user
  name          TEXT NOT NULL,
  aliases       TEXT[] DEFAULT '{}',
  wikidata_qid  TEXT UNIQUE,
  country       CHAR(2),
  description   TEXT,
  attributes    JSONB DEFAULT '{}',        -- p.ej. ticker, ISIN, cargo actual, tradición intelectual
  embedding     vector(1024),
  created_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON entity USING gin (name gin_trgm_ops);

CREATE TABLE edge (
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  src_id       UUID REFERENCES entity(id),
  dst_id       UUID REFERENCES entity(id),
  rel          TEXT NOT NULL,              -- member_of|leads|funds|allied_with|sanctions|trades_with|cites|influenced_by|owns|exposed_to|opposes|supports|votes_for|votes_against|subsidiary_of|supplies
  weight       REAL,
  valid_from   DATE,
  valid_to     DATE,
  confidence   REAL,
  source_doc_id UUID REFERENCES document(id),
  attributes   JSONB DEFAULT '{}'
);
CREATE INDEX ON edge (src_id, rel);
CREATE INDEX ON edge (dst_id, rel);

CREATE TABLE document_entity (
  document_id UUID REFERENCES document(id),
  entity_id   UUID REFERENCES entity(id),
  salience    REAL,
  PRIMARY KEY (document_id, entity_id)
);

-- ───────────────────────── EVENTOS ─────────────────────────
CREATE TABLE event (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title_neutral   TEXT NOT NULL,
  summary         TEXT,
  domain          TEXT,                     -- politics|economy|conflict|society|technology|health|environment|law
  countries       CHAR(2)[] DEFAULT '{}',
  geo             JSONB,                    -- {lat, lon} o geometría
  first_seen_at   TIMESTAMPTZ,
  last_update_at  TIMESTAMPTZ,
  status          TEXT DEFAULT 'developing',-- developing|stable|resolved|merged
  merged_into     UUID REFERENCES event(id),
  materiality     REAL,                     -- 0-100
  materiality_breakdown JSONB,
  coverage_stats  JSONB,                    -- por ecosistema, región, idioma, tipo
  silence_index   JSONB,
  centroid        vector(1024),
  parent_event_id UUID REFERENCES event(id) -- historias largas (p.ej. "guerra en Ucrania")
);
CREATE INDEX ON event (last_update_at DESC);
CREATE INDEX ON event USING hnsw (centroid vector_cosine_ops);

CREATE TABLE event_document (
  event_id    UUID REFERENCES event(id),
  document_id UUID REFERENCES document(id),
  similarity  REAL,
  PRIMARY KEY (event_id, document_id)
);

-- ───────────────────────── AFIRMACIONES ─────────────────────────
CREATE TABLE claim (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  event_id        UUID REFERENCES event(id),
  text_canonical  TEXT NOT NULL,            -- afirmación atómica normalizada en español
  level           TEXT NOT NULL,            -- fact|data|academic|opinion
  status          TEXT NOT NULL DEFAULT 'unverified', -- confirmed|disputed|refuted|unverified
  check_worthy    REAL,
  first_source_doc UUID REFERENCES document(id),
  first_seen_at   TIMESTAMPTZ,
  primary_evidence_doc UUID REFERENCES document(id),
  embedding       vector(1024),
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE claim_evidence (
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  claim_id     UUID REFERENCES claim(id),
  document_id  UUID REFERENCES document(id),
  stance       TEXT NOT NULL,              -- supports|refutes|mentions|qualifies
  quote        TEXT,                        -- fragmento breve literal
  quote_offset INT4RANGE,
  extracted_by TEXT,                        -- modelo+versión de prompt
  confidence   REAL,
  created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE claim_revision (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  claim_id    UUID REFERENCES claim(id),
  old_status  TEXT,
  new_status  TEXT,
  reason      TEXT,
  evidence_ids UUID[],
  changed_at  TIMESTAMPTZ DEFAULT now()
);

-- ───────────────────────── MARCOS / NARRATIVAS ─────────────────────────
CREATE TABLE frame (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  event_id        UUID REFERENCES event(id),
  label           TEXT,
  problem         TEXT,     -- Entman: definición del problema
  cause           TEXT,     -- atribución causal
  moral_judgment  TEXT,
  remedy          TEXT,
  evidence_offered TEXT,
  embedding       vector(1024)
);
CREATE TABLE document_frame (
  document_id UUID REFERENCES document(id),
  frame_id    UUID REFERENCES frame(id),
  strength    REAL,
  PRIMARY KEY (document_id, frame_id)
);

-- ───────────────────────── VARIABLES DE ESTADO ─────────────────────────
CREATE TABLE state_variable (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  scope       TEXT NOT NULL,              -- ISO país, bloque o 'world'
  dimension   TEXT NOT NULL,              -- POWER|RULES|MONEY|FORCE|LEGITIMACY|EXTERNAL|STRUCTURE
  key         TEXT NOT NULL,              -- p.ej. 'policy_rate', 'gov_coalition_seats', 'acled_events_30d'
  unit        TEXT,
  source_hint TEXT,
  threshold   JSONB,                      -- regla de cambio material
  UNIQUE (scope, key)
);
CREATE TABLE state_observation (
  variable_id UUID REFERENCES state_variable(id),
  observed_at TIMESTAMPTZ NOT NULL,
  value_num   DOUBLE PRECISION,
  value_text  TEXT,
  source_doc_id UUID REFERENCES document(id),
  PRIMARY KEY (variable_id, observed_at)
);
CREATE TABLE state_delta (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  variable_id UUID REFERENCES state_variable(id),
  event_id    UUID REFERENCES event(id),
  detected_at TIMESTAMPTZ DEFAULT now(),
  magnitude   REAL,                       -- en desviaciones típicas o unidades normalizadas
  description TEXT
);

-- ───────────────────────── ACTORES: POSICIONES ─────────────────────────
CREATE TABLE position_statement (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  actor_id    UUID REFERENCES entity(id),
  topic       TEXT NOT NULL,
  stance      REAL,                        -- -1..1 sobre el eje del tema
  quote       TEXT,
  document_id UUID REFERENCES document(id),
  said_at     TIMESTAMPTZ,
  kind        TEXT                          -- statement|vote|decision|policy
);

-- ───────────────────────── PRONÓSTICOS ─────────────────────────
CREATE TABLE forecast_question (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title           TEXT NOT NULL,
  resolution_criteria TEXT NOT NULL,
  resolution_source TEXT,
  kind            TEXT DEFAULT 'binary',   -- binary|multi|numeric|date
  options         JSONB,
  open_at         TIMESTAMPTZ DEFAULT now(),
  close_at        TIMESTAMPTZ NOT NULL,
  resolve_by      TIMESTAMPTZ,
  resolved_at     TIMESTAMPTZ,
  outcome         JSONB,
  origin_event_id UUID REFERENCES event(id),
  domain          TEXT,
  countries       CHAR(2)[],
  base_rate       REAL,
  base_rate_note  TEXT,
  market_links    JSONB                     -- [{venue, market_id, url}]
);
CREATE TABLE forecast (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  question_id   UUID REFERENCES forecast_question(id),
  forecaster    TEXT NOT NULL,              -- 'user'|'atlas_ensemble'|'agent:<name>'|'market:<venue>'|'acled_cast'|'expert:<entity_id>'
  probability   REAL,
  distribution  JSONB,
  rationale     TEXT,
  evidence_ids  UUID[],
  made_at       TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON forecast (question_id, made_at);
CREATE TABLE forecast_score (
  question_id UUID REFERENCES forecast_question(id),
  forecaster  TEXT,
  brier       REAL,
  log_score   REAL,
  PRIMARY KEY (question_id, forecaster)
);

-- ───────────────────────── IDEAS / ARGUMENTOS / HISTORIA ─────────────────────────
CREATE TABLE argument_node (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  map_id      UUID NOT NULL,
  kind        TEXT NOT NULL,               -- thesis|premise|objection|reply|evidence|author|work
  text        TEXT NOT NULL,
  author_entity_id UUID REFERENCES entity(id),
  work_entity_id UUID REFERENCES entity(id),
  is_user     BOOLEAN DEFAULT FALSE,
  created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE argument_edge (
  map_id  UUID NOT NULL,
  src     UUID REFERENCES argument_node(id),
  dst     UUID REFERENCES argument_node(id),
  rel     TEXT NOT NULL,                   -- supports|attacks|replies|instantiates
  PRIMARY KEY (map_id, src, dst, rel)
);
CREATE TABLE historical_case (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name        TEXT NOT NULL,
  category    TEXT,
  start_date  DATE,
  end_date    DATE,
  countries   CHAR(2)[],
  variables   JSONB,
  outcome     TEXT,
  sources     JSONB,
  embedding   vector(1024)
);

-- ───────────────────────── USUARIO: TALLER / DIETA / MANDO ─────────────────────────
CREATE TABLE note (
  id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title      TEXT,
  body_json  JSONB,                        -- TipTap
  body_text  TEXT,
  links      UUID[],                       -- entidades/eventos enlazados
  course     TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  embedding  vector(1024)
);
CREATE TABLE review_card (
  id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  front      TEXT, back TEXT, source_ref JSONB,
  fsrs_state JSONB, due_at TIMESTAMPTZ
);
CREATE TABLE reading_log (
  id          BIGSERIAL PRIMARY KEY,
  document_id UUID REFERENCES document(id),
  event_id    UUID REFERENCES event(id),
  action      TEXT,                        -- open|read|highlight|save|share
  seconds     INT,
  at          TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE business_unit (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name        TEXT NOT NULL,
  sectors     TEXT[],
  jurisdictions TEXT[],
  markets     TEXT[],
  currencies  TEXT[],
  regulations TEXT[],
  suppliers   JSONB,
  keywords    TEXT[],
  entity_id   UUID REFERENCES entity(id)
);
CREATE TABLE exposure_alert (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  business_id UUID REFERENCES business_unit(id),
  event_id    UUID REFERENCES event(id),
  channel     TEXT,                        -- regulatory|tax|fx|supply_chain|demand|reputation|competition
  explanation TEXT,
  confidence  REAL,
  created_at  TIMESTAMPTZ DEFAULT now(),
  dismissed   BOOLEAN DEFAULT FALSE
);
CREATE TABLE decision_log (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  business_id UUID REFERENCES business_unit(id),
  title       TEXT, context TEXT,
  premises    JSONB, alternatives JSONB,
  success_probability REAL,
  premortem   TEXT,
  decided_at  TIMESTAMPTZ DEFAULT now(),
  review_at   TIMESTAMPTZ,
  outcome     TEXT, lessons TEXT
);

-- ───────────────────────── OBSERVABILIDAD ─────────────────────────
CREATE TABLE llm_call (
  id          BIGSERIAL PRIMARY KEY,
  at          TIMESTAMPTZ DEFAULT now(),
  module      TEXT, agent TEXT, prompt_name TEXT, prompt_version TEXT,
  model       TEXT,
  input_tokens INT, output_tokens INT, cache_read_tokens INT, cache_write_tokens INT,
  cost_usd    NUMERIC(10,5),
  latency_ms  INT,
  ok          BOOLEAN, error TEXT
);
CREATE TABLE job_run (
  id          BIGSERIAL PRIMARY KEY,
  job         TEXT, started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ,
  ok          BOOLEAN, stats JSONB, error TEXT
);
