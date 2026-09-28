/* Cliente HTTP mínimo para la API de ATLAS. Todas las rutas cuelgan de /api (proxy en desarrollo, mismo origen en producción). */

import type {
  ActorDetail,
  Actor,
  AgentsStatus,
  AlertsResponse,
  ArgumentMap,
  Brief,
  BriefLatest,
  CalibrationResponse,
  CaseCompare,
  CountryRow,
  CountrySheet,
  DietReport,
  DiffResponse,
  DocumentDetail,
  EnsembleOutput,
  EventDetail,
  EventSummary,
  ForecastQuestion,
  Genealogy,
  HistoricalCase,
  MachineResponse,
  MandoResponse,
  MapDetail,
  MarketsResponse,
  NormativeTranslation,
  Note,
  PrimariesResponse,
  PrismResponse,
  RadarResponse,
  RedTeamReport,
  ReviewCard,
  SearchResponse,
  Settings,
  WhatIfOutput,
} from './types'

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, detail: unknown, message?: string) {
    super(message ?? `HTTP ${status}`)
    this.status = status
    this.detail = detail
  }
  /** Mensaje legible para el usuario (extrae `detail.message` o `detail`). */
  get userMessage(): string {
    const d = this.detail as { message?: string; detail?: unknown } | string | null
    if (typeof d === 'string') return d
    if (d && typeof d === 'object') {
      if (typeof d.message === 'string') return d.message
      if (typeof d.detail === 'string') return d.detail
      const inner = d.detail as { message?: string } | undefined
      if (inner && typeof inner.message === 'string') return inner.message
      if (Array.isArray((d as { issues?: unknown }).issues)) return ((d as { issues: string[] }).issues).join(' ')
    }
    return this.message
  }
  get agentsDisabled(): boolean {
    return this.status === 409
  }
}

async function request<T>(method: string, path: string, body?: unknown, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body !== undefined ? { 'content-type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    ...init,
  })
  const ct = res.headers.get('content-type') || ''
  const payload: unknown = ct.includes('application/json') ? await res.json().catch(() => null) : await res.text().catch(() => null)
  if (!res.ok) {
    const detail = payload && typeof payload === 'object' && 'detail' in (payload as object) ? (payload as { detail: unknown }).detail : payload
    throw new ApiError(res.status, detail, typeof detail === 'string' ? detail : `HTTP ${res.status}`)
  }
  return payload as T
}

const qs = (params: Record<string, string | number | boolean | null | undefined>): string => {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue
    p.set(k, String(v))
  }
  const s = p.toString()
  return s ? `?${s}` : ''
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  del: <T>(path: string) => request<T>('DELETE', path),

  health: () => request<{ status: string; llm_enabled: boolean; counts: Record<string, number>; version: string }>('GET', '/health'),

  // Analista
  radar: (p: { hours: number; domain?: string; country?: string; limit?: number }) => request<RadarResponse>('GET', `/radar${qs(p)}`),
  events: (p: { hours?: number; limit?: number; q?: string; country?: string; domain?: string; offset?: number }) => request<{ events: EventSummary[] }>('GET', `/events${qs(p)}`),
  event: (id: string) => request<EventDetail>('GET', `/events/${id}`),
  flagEvent: (id: string, flag: 'important' | 'noise' | '') => request<{ ok: boolean }>('POST', `/events/${id}/flag`, { flag }),
  prism: (id: string) => request<PrismResponse>('GET', `/events/${id}/prism`),
  primaries: (p: { hours?: number; source_slug?: string; country?: string; kind?: string; limit?: number }) => request<PrimariesResponse>('GET', `/primaries${qs(p)}`),
  document: (id: string) => request<DocumentDetail>('GET', `/documents/${id}`),
  diff: (oldId: string, newId: string) => request<DiffResponse>('GET', `/diff${qs({ old: oldId, new: newId })}`),
  markets: () => request<MarketsResponse>('GET', '/markets'),
  followMarket: (id: string, follow: boolean) => request<{ ok: boolean }>('POST', `/markets/prediction/${id}/follow${qs({ follow })}`),
  countries: () => request<{ countries: CountryRow[]; blocs: string[] }>('GET', '/countries'),
  country: (iso2: string, days: number) => request<CountrySheet>('GET', `/countries/${iso2}${qs({ days })}`),
  actors: (p: { q?: string; kind?: string; limit?: number }) => request<{ actors: Actor[] }>('GET', `/actors${qs(p)}`),
  actor: (id: string, days = 30) => request<ActorDetail>('GET', `/actors/${id}${qs({ days })}`),

  // Pensador
  maps: () => request<{ maps: ArgumentMap[] }>('GET', '/agora/maps'),
  createMap: (body: { title: string; topic?: string }) => request<{ id: string }>('POST', '/agora/maps', body),
  map: (id: string) => request<MapDetail>('GET', `/agora/maps/${id}`),
  addNode: (mapId: string, body: { kind: string; text: string; author?: string; work?: string; x?: number; y?: number }) => request<{ id: string }>('POST', `/agora/maps/${mapId}/nodes`, body),
  updateNode: (id: string, body: { text?: string; x?: number; y?: number; author?: string; work?: string }) => request<{ ok: boolean }>('PUT', `/agora/nodes/${id}`, body),
  deleteNode: (id: string) => request<{ ok: boolean }>('DELETE', `/agora/nodes/${id}`),
  addEdge: (mapId: string, body: { src: string; dst: string; rel: string }) => request<{ id: string }>('POST', `/agora/maps/${mapId}/edges`, body),
  deleteEdge: (id: string) => request<{ ok: boolean }>('DELETE', `/agora/edges/${id}`),
  genealogy: () => request<Genealogy>('GET', '/agora/genealogy'),
  cases: (p: { q?: string; category?: string }) => request<{ cases: HistoricalCase[]; categories: string[] }>('GET', `/archive/cases${qs(p)}`),
  analogs: (p: { q?: string; event_id?: string; category?: string; n?: number }) => request<{ query: string; analogs: HistoricalCase[]; compare: CaseCompare | null; note: string }>('GET', `/archive/analogs${qs(p)}`),
  forecasts: (status?: string) => request<{ questions: ForecastQuestion[] }>('GET', `/forecasts${qs({ status })}`),
  forecast: (id: string) => request<ForecastQuestion>('GET', `/forecasts/${id}`),
  createQuestion: (body: Record<string, unknown>) => request<{ id: string }>('POST', '/forecasts', body),
  addForecast: (id: string, probability: number, rationale?: string) => request<{ ok: boolean; system_probability: number | null }>('POST', `/forecasts/${id}/forecast`, { probability, rationale, forecaster: 'user' }),
  resolveQuestion: (id: string, outcome: 0 | 1, note?: string) => request<{ ok: boolean; scores: Record<string, { brier: number; log_score: number; p: number }> }>('POST', `/forecasts/${id}/resolve`, { outcome, note }),
  linkMarket: (id: string, market_id: string) => request<{ ok: boolean }>('POST', `/forecasts/${id}/link_market`, { market_id }),
  calibration: (forecaster = 'user') => request<CalibrationResponse>('GET', `/forecasts/calibration${qs({ forecaster })}`),
  notes: (q?: string) => request<{ notes: Note[] }>('GET', `/notes${qs({ q })}`),
  note: (id: string) => request<Note>('GET', `/notes/${id}`),
  createNote: (body: { title?: string; body_text: string; course?: string }) => request<{ id: string }>('POST', '/notes', body),
  updateNote: (id: string, body: { title?: string; body_text: string; course?: string }) => request<{ ok: boolean }>('PUT', `/notes/${id}`, body),
  deleteNote: (id: string) => request<{ ok: boolean }>('DELETE', `/notes/${id}`),
  cards: (dueOnly: boolean) => request<{ cards: ReviewCard[]; due: number }>('GET', `/cards${qs({ due_only: dueOnly })}`),
  createCard: (body: { front: string; back: string; source_ref?: Record<string, unknown> }) => request<{ id: string }>('POST', '/cards', body),
  reviewCard: (id: string, rating: 1 | 2 | 3 | 4) => request<{ ok: boolean; state: Record<string, number>; due_at: string }>('POST', `/cards/${id}/review`, { rating }),
  deleteCard: (id: string) => request<{ ok: boolean }>('DELETE', `/cards/${id}`),

  // CEO y transversales
  mando: () => request<MandoResponse>('GET', '/mando'),
  dismissAlert: (id: string) => request<{ ok: boolean }>('POST', `/mando/alerts/${id}/dismiss`),
  createDecision: (body: Record<string, unknown>) => request<{ id: string }>('POST', '/mando/decisions', body),
  decisionOutcome: (id: string, body: { outcome: string; lessons?: string }) => request<{ ok: boolean }>('POST', `/mando/decisions/${id}/outcome`, body),
  dietLog: (body: { document_id?: string; event_id?: string; action: 'open' | 'read'; seconds?: number }, keepalive = false) => request<{ ok: boolean }>('POST', '/diet/log', body, { keepalive }),
  dietReport: (days: number) => request<DietReport>('GET', `/diet/report${qs({ days })}`),
  briefLatest: (kind: 'study' | 'executive') => request<BriefLatest>('GET', `/brief/latest${qs({ kind })}`),
  brief: (id: string) => request<{ brief: Brief }>('GET', `/brief/${id}`),
  briefGenerate: (kind: 'study' | 'executive', hours = 24) => request<{ brief: Brief }>('POST', `/brief/generate${qs({ kind, hours })}`),
  machine: () => request<MachineResponse>('GET', '/machine'),
  machineRunning: () => request<Record<string, boolean>>('GET', '/machine/running'),
  ingest: (force = false) => request<{ started: boolean; reason?: string }>('POST', `/machine/ingest${qs({ force })}`),
  refreshMarkets: () => request<{ started: boolean; reason?: string }>('POST', '/machine/markets'),
  recompute: (hours = 72) => request<Record<string, unknown>>('POST', `/machine/recompute${qs({ hours })}`),
  toggleSource: (id: string) => request<{ active: number }>('POST', `/machine/sources/${id}/toggle`),
  alerts: () => request<AlertsResponse>('GET', '/alerts'),
  alertsRead: () => request<{ ok: boolean }>('POST', '/alerts/read'),
  settings: () => request<Settings>('GET', '/settings'),
  putSettings: (body: Partial<Settings>) => request<Partial<Settings>>('PUT', '/settings', body),
  search: (q: string, limit = 6) => request<SearchResponse>('GET', `/search${qs({ q, limit })}`),

  // Agentes con salida estructurada (los de streaming van por sse.ts)
  agentsStatus: () => request<AgentsStatus>('GET', '/agents/status'),
  redTeam: (eventId: string) => request<RedTeamReport>('POST', `/agents/red_team/${eventId}`),
  normative: (eventId: string) => request<NormativeTranslation>('POST', `/agents/normative/${eventId}`),
  whatIf: (body: { premise: string; event_id?: string | null }) => request<WhatIfOutput>('POST', '/agents/what_if', body),
  ensemble: (questionId: string) => request<EnsembleOutput>('POST', `/agents/forecast_ensemble/${questionId}`),
  briefRedact: (briefId: string) => request<{ brief_id: string; cost_usd: number; model: string; redaction_md: string }>('POST', `/agents/brief_redact/${briefId}`),
}
