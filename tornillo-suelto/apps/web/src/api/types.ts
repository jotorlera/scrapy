/* Tipos derivados de las respuestas reales de la API (services/core/atlas_core/api/*.py).
   Se tipa lo que usa la interfaz; `unknown` donde no importa. */

export type Domain = 'politics' | 'economy' | 'conflict' | 'society' | 'technology' | 'health' | 'environment' | 'law'
export type ClaimLevel = 'fact' | 'data' | 'academic' | 'opinion'
export type ClaimStatus = 'confirmed' | 'disputed' | 'unverified' | 'refuted' | 'denied' | string
export type Mode = 'ANALISTA' | 'PENSADOR' | 'CEO'

export interface AxisCell {
  expected: number
  observed: number
  s: number
  silent: boolean
  over: boolean
}

export interface Silence {
  axis: string
  ecosystem: string
  expected: number
  observed: number
  s: number
  [k: string]: unknown
}

export interface CoverageStats {
  n_docs: number
  axes: Record<string, Record<string, AxisCell>>
  matrix: Record<string, Record<string, number>>
  silences: Silence[]
  n_primary: number
  n_sources: number
  langs: string[]
  topics: string[]
}

export interface MaterialityBreakdown {
  score: number
  beta0: number
  features: Record<string, number>
  contributions: Record<string, number>
  user_bonus_points: number
  user_reasons: string[]
  n_docs: number
  n_sources: number
  single_source: boolean
  n_independent_sources: number
  blocs: string[]
  method: string
}

export interface EventSummary {
  id: string
  title_neutral: string
  title_source: 'lead_document' | 'llm' | string
  summary: string | null
  domain: Domain | string | null
  countries: string[]
  geo: { lat: number; lon: number } | null
  first_seen_at: string | null
  last_update_at: string | null
  status: string
  materiality: number | null
  materiality_breakdown: MaterialityBreakdown | null
  coverage_stats: CoverageStats | null
  silence_index: unknown
  n_docs: number
  lead_document_id: string | null
  entity_keys: string[]
  user_flag: string | null
  n_sources: number
  n_primary: number
  langs: string[]
  silences: Silence[]
  topics: string[]
  ecosystems: Record<string, number>
  shared_entities?: number
}

export interface Delta {
  id: string
  variable_id: string
  event_id: string | null
  detected_at: string
  magnitude: number | null
  description: string | null
  source_doc_id: string | null
  scope: string
  dimension: string
  key: string
  unit?: string | null
  source_hint?: string | null
  event_title?: string | null
  source_url?: string | null
  source_title?: string | null
}

export interface RadarResponse {
  events: EventSummary[]
  deltas: Delta[]
  counts: { events: number; documents: number; sources_ok: number }
  by_domain: Record<string, number>
  hours: number
}

export interface DocumentOut {
  id: string
  source_id: string
  kind: string
  url: string
  canonical_url: string | null
  title: string | null
  lede: string | null
  lang: string | null
  authors: string[]
  published_at: string | null
  fetched_at: string
  paywalled: number
  countries: string[]
  event_id: string | null
  meta: Record<string, unknown>
  source_name?: string
  source_slug?: string
  tier?: number
  source_type?: string
  ideology_label?: string | null
  region_bloc?: string | null
  state_relation?: string | null
  source_country?: string | null
  paywall?: string | null
  salience?: number
  hits?: string[]
}

export interface DocumentDetail extends DocumentOut {
  text: string | null
  claims: Array<{ id: string; text_canonical: string; level: ClaimLevel; status: ClaimStatus; quote: string; attributed_to: string | null; extracted_by: string }>
}

export interface ClaimEvidence {
  id: string
  stance: 'supports' | 'contradicts' | string
  quote: string
  extracted_by: string | null
  confidence: number | null
  created_at: string
  document_id: string
  doc_title: string | null
  doc_url: string
  published_at: string | null
  source_name: string
  source_tier: number
  ideology_label: string | null
  region_bloc: string | null
  source_id: string
}

export interface ClaimRevision {
  id: string
  claim_id: string
  old_status: string | null
  new_status: string | null
  reason: string | null
  evidence_ids: string[]
  changed_at: string
}

export interface Claim {
  id: string
  event_id: string | null
  document_id: string
  text_canonical: string
  text_original: string | null
  level: ClaimLevel
  status: ClaimStatus
  check_worthy: number
  attributed_to: string | null
  extracted_by: string
  first_seen_at: string | null
  created_at: string
  doc_title: string | null
  doc_url: string
  source_name: string
  source_tier: number
  evidence: ClaimEvidence[]
  revisions: ClaimRevision[]
}

export interface TimelineItem {
  t: string | null
  kind: 'document' | 'revision'
  title: string
  source: string
  tier: number | null
  url: string | null
  id: string
}

export interface ForecastQuestion {
  id: string
  title: string
  resolution_criteria: string
  resolution_source: string | null
  kind: string
  options: unknown
  open_at: string
  close_at: string
  resolve_by: string | null
  resolved_at: string | null
  outcome: { value: number; note?: string | null } | null
  origin_event_id: string | null
  domain: string | null
  countries: string[]
  base_rate: number | null
  base_rate_note: string | null
  market_links: Array<{ id: string; venue: string; url: string | null }>
  status: 'open' | 'resolved' | string
  created_by: string | null
  latest: Record<string, { p: number; at: string; rationale: string | null }>
  series: Array<{ forecaster: string; probability: number; rationale: string | null; made_at: string }>
  scores: Array<{ question_id: string; forecaster: string; brier: number; log_score: number }>
  market: { probability: number | null; venue: string; url: string | null; fetched_at: string } | null
  origin_event?: EventSummary | null
}

/* En el detalle de evento las preguntas llegan con `latest` simplificado (forecaster → probabilidad). */
export interface EventQuestion {
  id: string
  title: string
  status: string
  close_at: string
  origin_event_id: string | null
  countries: string[]
  market_links: Array<{ id: string; venue: string; url: string | null }>
  latest: Record<string, number>
}

export interface HistoricalCase {
  id: string
  name: string
  category: string
  start_date: string | null
  end_date: string | null
  countries: string[]
  variables: Record<string, unknown>
  outcome: string | null
  duration_months: number | null
  summary: string | null
  sources: string[]
  similarity?: number
}

export interface CaseCompare {
  variables: Array<{ variable: string; values: unknown[]; agree: boolean }>
  outcomes: Array<{ name: string; outcome: string | null; duration_months: number | null }>
}

export interface PredictionMarket {
  id: string
  venue: string
  market_id: string
  question: string
  probability: number | null
  volume: number | null
  liquidity: number | null
  url: string | null
  close_at: string | null
  fetched_at: string
  tags: string[]
  followed: number
  overlap?: number
}

export interface ExposureAlert {
  id: string
  business_id: string
  event_id: string
  channel: string
  explanation: string | null
  confidence: number | null
  created_at: string
  dismissed: number
  business_name: string
  title_neutral?: string
  materiality?: number | null
  countries?: string[]
  domain?: string | null
}

export interface EventEntity {
  id: string
  kind: string
  name: string
  country: string | null
  salience: number
  n: number
}

export interface EventDetail {
  event: EventSummary
  documents: DocumentOut[]
  claims: Claim[]
  timeline: TimelineItem[]
  deltas: Delta[]
  related: EventSummary[]
  questions: EventQuestion[]
  exposures: ExposureAlert[]
  entities: EventEntity[]
  agent_runs: Array<{ id: string; kind: string; status: string; created_at: string; finished_at: string | null; cost_usd: number | null }>
  analogs: { cases: HistoricalCase[]; compare: CaseCompare | null }
  prediction_markets: PredictionMarket[]
}

export interface LexiconTerm {
  term: string
  z: number
  count: number
}

export interface PrismResponse {
  event: EventSummary
  matrix: { rows: string[]; cols: string[]; cells: Record<string, Record<string, number>> }
  axes: Record<string, Record<string, AxisCell>>
  silences: Silence[]
  lexicon: { ideology: Record<string, LexiconTerm[]>; bloc: Record<string, LexiconTerm[]> }
  state_media: Array<{ id: string; title: string; lede: string | null; lang: string | null; published_at: string | null; url: string; source_name: string; ideology_label: string | null; region_bloc: string | null; state_relation: string; stype: string; tier: number; country: string | null }>
  frames: unknown[]
  representative: Record<string, Array<{ source: string; title: string; url: string; lang: string | null; bloc: string | null }>>
  n_docs: number
  method: { silence: string; lexicon: string }
}

export interface PrimariesResponse {
  documents: DocumentOut[]
  sources: Array<{ slug: string; name: string; country: string | null; type: string; n: number; last: string | null }>
  lineages: Array<{ slug: string; name: string; n: number }>
}

export interface DiffOp {
  op: 'equal' | 'insert' | 'delete' | 'replace'
  old: string | null
  new: string | null
  inline?: Array<{ t: 'eq' | 'del' | 'ins'; s: string }> | null
}

export interface DiffResponse {
  ratio: number
  n_old: number
  n_new: number
  n_changed: number
  ops: DiffOp[]
  material_changes: Array<{ kind: 'changed' | 'added' | 'removed'; old: string | null; new: string | null }>
  summary: string
  method: string
  old: { id: string; title: string | null; published_at: string | null; url: string; lede: string | null }
  new: { id: string; title: string | null; published_at: string | null; url: string; lede: string | null }
}

export interface Quote {
  symbol: string
  label: string
  group_name: string
  price: number | null
  change_pct: number | null
  currency: string | null
  observed_at: string | null
  fetched_at: string | null
  source: string | null
  history: Array<{ t: string; v: number }>
  error: string | null
}

export interface CausalChannel {
  from: string
  to: string
  sign: string
  lag?: string
  ref?: string
}

export interface MarketsResponse {
  quotes: Quote[]
  prediction_markets: PredictionMarket[]
  channels: CausalChannel[]
  last_refresh: { finished_at: string | null; ok: number | null; stats: string | null } | null
  disclaimer: string
}

export interface CountryRow {
  iso2: string
  name: string
  name_en: string
  lat: number
  lon: number
  bloc: string
  level: 'A' | 'B' | 'C' | string
  events_7d: number
}

export interface StateVariable {
  id: string
  scope: string
  dimension: string
  key: string
  unit: string | null
  source_hint: string | null
  threshold: Record<string, unknown>
  last_value: number | null
  last_at: string | null
}

export interface CountrySheet {
  country: Omit<CountryRow, 'events_7d'>
  events: EventSummary[]
  deltas: Delta[]
  variables: StateVariable[]
  coverage: { local: number; foreign: number; by_bloc: Record<string, number> }
  questions: EventQuestion[]
  what_changed: EventSummary[]
  days: number
}

export interface Actor {
  id: string
  kind: string
  name: string
  country: string | null
  wikidata_qid: string | null
  attributes: Record<string, unknown>
  mentions_7d: number
}

export interface ActorDetail {
  entity: Actor & { aliases: string[]; description: string | null }
  documents: DocumentOut[]
  events: EventSummary[]
  attributed_claims: Array<{ id: string; text_canonical: string; level: ClaimLevel; status: ClaimStatus; attributed_to: string; first_seen_at: string | null; url: string; source_name: string }>
  co_mentions: Array<{ id: string; name: string; kind: string; n: number }>
}

export type NodeKind = 'thesis' | 'premise' | 'objection' | 'reply' | 'evidence' | 'author' | 'work'
export type EdgeRel = 'supports' | 'attacks' | 'replies' | 'instantiates'

export interface ArgumentMap {
  id: string
  title: string
  topic: string | null
  created_at: string
  n_nodes?: number
}
export interface ArgumentNode {
  id: string
  map_id: string
  kind: NodeKind
  text: string
  author: string | null
  work: string | null
  is_user: number
  x: number | null
  y: number | null
  created_at: string
}
export interface ArgumentEdge {
  id: string
  map_id: string
  src: string
  dst: string
  rel: EdgeRel
}
export interface MapDetail {
  map: ArgumentMap
  nodes: ArgumentNode[]
  edges: ArgumentEdge[]
  analysis: {
    unsupported: Array<{ id: string; text: string }>
    unanswered_objections: Array<{ id: string; text: string }>
    support_cycles: string[][]
  }
}

export interface Genealogy {
  title: string
  nodes: Array<{ id: string; label: string; years: string; work: string; concept: string }>
  edges: Array<[string, string, string]>
}

export interface CalibrationBin {
  lo: number
  hi: number
  n: number
  mean_p: number | null
  freq: number | null
  ci: [number, number] | null
}
export interface CalibrationResponse {
  forecaster: string
  calibration: { n: number; bins: CalibrationBin[]; brier: number | null; reliability: number | null; resolution: number | null; uncertainty: number | null }
  forecasters: string[]
  summary: Array<{ forecaster: string; n: number; brier: number; log_score: number; bss_vs_base_rate: number | null }>
}

export interface Note {
  id: string
  title: string | null
  body_text: string
  links: string[]
  course: string | null
  created_at: string
  updated_at: string
  backlinks?: Note[]
  linked_entities?: Array<{ id: string; kind: string; name: string }>
}

export interface ReviewCard {
  id: string
  front: string
  back: string
  source_ref: Record<string, unknown>
  fsrs_state: { interval?: number; ease?: number; reps?: number; lapses?: number }
  due_at: string
  created_at: string
}

export interface BusinessUnit {
  id: string
  name: string
  sectors: string[]
  jurisdictions: string[]
  markets: string[]
  currencies: string[]
  regulations: string[]
  keywords: string[]
  alerts_7d: number
}
export interface Decision {
  id: string
  business_id: string | null
  title: string
  context: string | null
  premises: string[]
  alternatives: string[]
  success_probability: number | null
  premortem: string | null
  decided_at: string
  review_at: string | null
  outcome: string | null
  lessons: string | null
  business_name: string | null
}
export interface MandoResponse {
  businesses: BusinessUnit[]
  alerts: ExposureAlert[]
  decisions: Decision[]
  regulatory: DocumentOut[]
  profile_note: string
}

export interface DietReport {
  days: number
  minutes: number
  n_logs: number
  entropy: Record<string, number>
  diversity_index: number
  distribution: Record<string, Record<string, number>>
  blind_spots: Array<{ topic: string; ecosystem: string; share: number; minutes: number }>
}

export interface BriefFact {
  text: string
  status: ClaimStatus
  level: ClaimLevel
  claim_id: string
  document_id: string
  source: string
  url: string
}
export interface BriefItem {
  event_id: string
  title: string
  materiality: number | null
  countries: string[]
  domain: string | null
  facts: BriefFact[]
  narrative_divergence: string
  primary_source: { title: string | null; url: string; name: string } | null
  why_it_matters: string
  course_concept: string | null
  exposures: Array<{ channel: string; confidence: number | null; name: string }>
}
export interface Brief {
  id: string
  date: string
  kind: string
  window_hours: number
  sections: Array<{ name: string; items: BriefItem[] }>
  n_events_considered: number
  forecast_prompt: { id: string; title: string; close_at: string } | null
  socratic_prompt: string
  reading_time_min: number
  composed_by: string
  created_at?: string
  redaction_md?: string
}
export interface BriefLatest {
  brief: Brief | null
  history?: Array<{ id: string; date: string; kind: string; composed_by: string; created_at: string }>
}

export interface BudgetState {
  daily_cap_usd: number
  spent_today_usd: number
  fraction: number
  pause_noncritical: boolean
  hard_stop: boolean
  enabled: boolean
  allocation: Record<string, number>
  limits: Record<string, unknown>
}
export interface AgentsStatus extends BudgetState {
  models: Record<string, string | null>
  message: string | null
}

export interface MachineSource {
  id: string
  slug: string
  name: string
  tier: number
  type: string
  country: string | null
  region_bloc: string | null
  active: number
  feeds: string[]
  feed_status: string | null
  poll_minutes: number
  last_polled_at: string | null
  last_ok_at: string | null
  last_error: string | null
  last_items: number
  docs_24h: number
}
export interface JobRun {
  id: number
  job: string
  started_at: string
  finished_at: string | null
  ok: number | null
  stats: Record<string, unknown>
  error: string | null
}
export interface MachineResponse {
  sources: MachineSource[]
  jobs: JobRun[]
  budget: BudgetState
  llm_cost: Array<{ day: string; module: string | null; model: string | null; n: number; cost: number | null; input_tokens: number | null; output_tokens: number | null; cache_read: number | null }>
  llm_recent: Array<{ id: number; at: string; module: string | null; agent: string | null; model: string | null; input_tokens: number | null; output_tokens: number | null; cache_read_tokens: number | null; cost_usd: number | null; latency_ms: number | null; ok: number | null; error: string | null }>
  totals: Record<string, number>
  embedder: string
}

export interface AlertsResponse {
  alerts: Array<{ id: string; kind: string; title: string; body: string | null; ref: Record<string, unknown>; created_at: string; read: number }>
  high_materiality: EventSummary[]
  unread: number
}

export interface Settings {
  theme: 'light' | 'dark'
  mode: Mode
  cat_enabled: boolean
  density: 'compact' | 'comfortable'
  brief_hour: string
}

export interface SearchResponse {
  events: EventSummary[]
  documents: DocumentOut[]
  entities: Array<{ id: string; kind: string; name: string; country: string | null }>
  notes: Array<{ id: string; title: string | null; updated_at: string }>
  questions: Array<{ id: string; title: string; status: string; close_at: string }>
  cases: Array<{ id: string; name: string; category: string; start_date: string | null }>
  countries: Array<{ iso2: string; name: string }>
}

/* Salidas estructuradas de agentes */
export interface RedTeamReport {
  strongest_alternative: string
  discriminating_evidence: string[]
  likely_biases: string[]
  tail_risks: Array<{ description: string; rough_probability: number }>
  question_nobody_asks: string
  cost_usd?: number
  model?: string
}
export interface NormativeTranslation {
  event_id: string
  questions: Array<{ question: string; traditions: Array<{ name: string; key_works: string[]; position_sketch: string }> }>
  uncertainties: string[]
  cost_usd?: number
  model?: string
}
export interface WhatIfOutput {
  scenarios: Array<{ name: string; probability: number; triggers: string[]; early_signals: string[]; description: string }>
  red_team_objection: string
  uncertainties: string[]
  label: string
  cost_usd?: number
}
export interface EnsembleOutput {
  question_id?: string
  individual: Array<{ approach: string; probability?: number | null; output?: Record<string, unknown> | null; cost_usd?: number; error?: string }>
  aggregate?: { raw: number; extremized: number; a: number }
  market?: number | null
  final?: number
  aggregator?: Record<string, unknown> | null
  error?: string
}

/* Eventos SSE de los agentes */
export type AgentEvent =
  | { type: 'start'; run_id: string; agent: string; model: string | null }
  | { type: 'delta'; text: string }
  | { type: 'done'; run_id: string; text: string }
  | { type: 'error'; message: string }
