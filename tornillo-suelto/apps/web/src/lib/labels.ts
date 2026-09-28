/* Etiquetas en español para los valores categóricos de la API. */

import type { ClaimLevel, ClaimStatus } from '../api/types'

export const DOMAIN_LABEL: Record<string, string> = {
  politics: 'Política',
  economy: 'Economía',
  conflict: 'Conflicto',
  society: 'Sociedad',
  technology: 'Tecnología',
  health: 'Salud',
  environment: 'Medio ambiente',
  law: 'Ley',
}
export const DOMAINS = Object.keys(DOMAIN_LABEL)

export const domainLabel = (d: string | null | undefined): string => (d ? (DOMAIN_LABEL[d] ?? d) : '—')
export const domainColor = (d: string | null | undefined): string => `var(--dom-${d && DOMAIN_LABEL[d] ? d : 'society'})`

export const IDEOLOGY_LABEL: Record<string, string> = {
  left: 'Izquierda',
  center_left: 'Centro-izquierda',
  center: 'Centro',
  center_right: 'Centro-derecha',
  right: 'Derecha',
  heterodox: 'Heterodoxo',
  institutional: 'Institucional',
  unknown: 'Sin clasificar',
}
export const IDEOLOGY_ORDER = ['left', 'center_left', 'center', 'center_right', 'right', 'heterodox', 'institutional', 'unknown']
export const ideologyLabel = (k: string | null | undefined): string => (k ? (IDEOLOGY_LABEL[k] ?? k) : 'Sin clasificar')

export const BLOC_LABEL: Record<string, string> = {
  anglo: 'Anglosajón',
  eu: 'UE',
  es: 'España',
  latam: 'Latam',
  arab: 'Mundo árabe',
  turkey: 'Turquía',
  russia: 'Rusia',
  china: 'China',
  india: 'India',
  japan_korea: 'Japón y Corea',
  other_asia: 'Resto de Asia',
  africa: 'África',
  oceania: 'Oceanía',
  global: 'Global',
}
export const blocLabel = (k: string | null | undefined): string => (k ? (BLOC_LABEL[k] ?? k) : 'Global')

export const SOURCE_TYPE_LABEL: Record<string, string> = {
  wire: 'Agencia',
  newspaper: 'Prensa',
  state_media: 'Medio estatal',
  digital_native: 'Nativo digital',
  broadcaster: 'Radiotelevisión',
  magazine: 'Revista',
  think_tank: 'Think tank',
  institution: 'Institución',
  court: 'Tribunal',
  statistical_office: 'Oficina estadística',
  central_bank: 'Banco central',
  intl_org: 'Organismo internacional',
  data_api: 'API de datos',
  academic: 'Académico',
  newsletter: 'Boletín',
}
export const sourceTypeLabel = (k: string | null | undefined): string => (k ? (SOURCE_TYPE_LABEL[k] ?? k) : '—')
export const PRIMARY_TYPES = new Set(['institution', 'central_bank', 'court', 'statistical_office', 'intl_org'])

export const STATE_RELATION_LABEL: Record<string, string> = {
  independent: 'Independiente',
  public_service_independent: 'Servicio público independiente',
  state_controlled: 'Control estatal',
  state_aligned: 'Alineado con el Estado',
}
export const stateRelationLabel = (k: string | null | undefined): string => (k ? (STATE_RELATION_LABEL[k] ?? k) : 'Sin dato')

export const PAYWALL_LABEL: Record<string, string> = { none: 'Abierto', metered: 'Con límite', hard: 'Muro de pago' }
export const paywallLabel = (k: string | null | undefined): string => (k ? (PAYWALL_LABEL[k] ?? k) : 'Abierto')

export const DOC_KIND_LABEL: Record<string, string> = {
  official_doc: 'Documento oficial',
  statement: 'Comunicado',
  dataset_release: 'Publicación de datos',
  paper: 'Artículo académico',
  article: 'Artículo',
}
export const docKindLabel = (k: string | null | undefined): string => (k ? (DOC_KIND_LABEL[k] ?? k) : '—')

export const DIMENSION_LABEL: Record<string, string> = {
  MONEY: 'Dinero',
  POWER: 'Poder',
  RULES: 'Reglas',
  FORCE: 'Fuerza',
  EXTERNAL: 'Exterior',
  LEGITIMACY: 'Legitimidad',
}
export const dimensionLabel = (k: string | null | undefined): string => (k ? (DIMENSION_LABEL[k] ?? k) : '—')

export const LEVEL_LABEL: Record<ClaimLevel, string> = { fact: 'HECHO', data: 'DATO', academic: 'ACADÉMICO', opinion: 'OPINIÓN' }
export const levelLabel = (l: string): string => LEVEL_LABEL[l as ClaimLevel] ?? l.toUpperCase()

export type StatusKind = 'confirmed' | 'disputed' | 'denied' | 'unverified'
export function statusKind(s: ClaimStatus | null | undefined): StatusKind {
  if (s === 'confirmed') return 'confirmed'
  if (s === 'disputed') return 'disputed'
  if (s === 'refuted' || s === 'denied' || s === 'false') return 'denied'
  return 'unverified'
}
export const STATUS_LABEL: Record<StatusKind, string> = { confirmed: 'Confirmada', disputed: 'Disputada', denied: 'Desmentida', unverified: 'Sin verificar' }
export const STATUS_GLYPH: Record<StatusKind, string> = { confirmed: '✓', disputed: '⚠', denied: '✕', unverified: '◌' }

export const AXIS_LABEL: Record<string, string> = { ideology: 'Ideología', bloc: 'Bloque', lang: 'Idioma', type: 'Tipo de fuente', state: 'Relación con el Estado' }
export const axisLabel = (k: string): string => AXIS_LABEL[k] ?? k

export function axisValueLabel(axis: string, v: string): string {
  if (axis === 'ideology') return ideologyLabel(v)
  if (axis === 'bloc') return blocLabel(v)
  if (axis === 'type') return sourceTypeLabel(v)
  if (axis === 'state') return stateRelationLabel(v)
  if (axis === 'lang') return v === 'unknown' ? 'Sin dato' : v
  return v
}

export const FEATURE_LABEL: Record<string, string> = {
  delta_state: 'Cambio de variable de estado',
  power: 'Peso de los actores',
  irreversibility: 'Irreversibilidad',
  breadth: 'Amplitud (países)',
  primary_document: 'Documento primario',
  novelty: 'Novedad',
  independent_coverage: 'Cobertura independiente',
  user_relevance: 'Relevancia para el usuario',
  virality_only: 'Solo viralidad',
  virality_only_penalty: 'Penalización por viralidad',
}
export const featureLabel = (k: string): string => FEATURE_LABEL[k] ?? k.replace(/_/g, ' ')

export const CHANNEL_LABEL: Record<string, string> = {
  regulatory: 'Regulatorio',
  fiscal: 'Fiscal',
  fx: 'Divisas',
  currency: 'Divisas',
  supply_chain: 'Cadena de suministro',
  demand: 'Demanda',
  reputation: 'Reputación',
  keyword: 'Palabra clave',
  sector: 'Sector',
  jurisdiction: 'Jurisdicción',
}
export const channelLabel = (k: string): string => CHANNEL_LABEL[k] ?? k

export const NODE_KIND_LABEL: Record<string, string> = {
  thesis: 'Tesis',
  premise: 'Premisa',
  objection: 'Objeción',
  reply: 'Réplica',
  evidence: 'Evidencia',
  author: 'Autor',
  work: 'Obra',
}
export const EDGE_REL_LABEL: Record<string, string> = { supports: 'apoya', attacks: 'ataca', replies: 'replica', instantiates: 'ejemplifica' }

export const FORECASTER_LABEL = (f: string): string => {
  if (f === 'user') return 'Tú'
  if (f === 'atlas_final') return 'ATLAS'
  if (f === 'base_rate') return 'Tasa base'
  if (f.startsWith('market:')) return `Mercado (${f.slice(7)})`
  if (f.startsWith('agent:')) return `Agente ${f.slice(6).replace(/_/g, ' ')}`
  if (f.startsWith('atlas_')) return `ATLAS ${f.slice(6).replace(/_/g, ' ')}`
  return f
}

export const TRADITIONS = [
  'Marxismo',
  'Liberalismo clásico',
  'Rawlsianismo',
  'Libertarismo',
  'Republicanismo (Pettit)',
  'Comunitarismo',
  'Conservadurismo (Burke, Oakeshott)',
  'Realismo (Morgenthau, Waltz, Mearsheimer)',
  'Liberalismo institucionalista (Keohane)',
  'Constructivismo (Wendt)',
  'Teoría crítica',
  'Escuela de Viena',
]

export const CASE_CATEGORY_LABEL: Record<string, string> = {
  debt_crisis: 'Crisis de deuda',
  hegemonic_transition: 'Transición de hegemonía',
  trade_war: 'Guerra comercial',
  sanctions: 'Sanciones',
  coup: 'Golpe de Estado',
  revolution: 'Revolución',
  hyperinflation: 'Hiperinflación',
  pandemic: 'Pandemia',
  secession_referendum: 'Referéndum de secesión',
  alliance_collapse: 'Colapso de alianza',
  ceasefire: 'Alto el fuego',
}
export const caseCategoryLabel = (k: string): string => CASE_CATEGORY_LABEL[k] ?? k.replace(/_/g, ' ')

/** Etiqueta de procedencia de un extractor (`heuristic:v1` → heurístico; `claude…` → modelo). */
export function extractorLabel(extractedBy: string | null | undefined): string {
  if (!extractedBy) return 'sin dato'
  if (extractedBy.startsWith('heuristic')) return 'heurístico'
  if (extractedBy.startsWith('claude')) return 'modelo'
  return extractedBy
}

export function titleSourceLabel(titleSource: string | null | undefined): string {
  if (titleSource === 'llm') return 'título neutro generado'
  return 'titular de la fuente principal'
}

export function composedByLabel(c: string | null | undefined): string {
  if (c === 'rules') return 'compuesto por reglas'
  if (c === 'llm') return 'redactado por el editor (modelo)'
  return c ? `compuesto por ${c}` : 'sin dato'
}
