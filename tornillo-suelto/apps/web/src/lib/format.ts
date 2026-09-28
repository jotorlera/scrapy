/* Formato de fechas y cifras (es-ES). */

const nf0 = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 0 })
const nf1 = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 1, minimumFractionDigits: 1 })
const nf2 = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 2, minimumFractionDigits: 2 })

export const fmtInt = (n: number | null | undefined): string => (n == null || Number.isNaN(n) ? '—' : nf0.format(n))
export const fmt1 = (n: number | null | undefined): string => (n == null || Number.isNaN(n) ? '—' : nf1.format(n))
export const fmt2 = (n: number | null | undefined): string => (n == null || Number.isNaN(n) ? '—' : nf2.format(n))
export const fmtPct = (p: number | null | undefined, digits = 0): string => (p == null || Number.isNaN(p) ? '—' : `${(p * 100).toFixed(digits)} %`)
export const fmtSignedPct = (p: number | null | undefined): string => {
  if (p == null || Number.isNaN(p)) return '—'
  const s = p > 0 ? '+' : ''
  return `${s}${p.toFixed(2)} %`
}
export const fmtUsd = (n: number | null | undefined): string => (n == null ? '—' : `${n.toFixed(n < 1 ? 4 : 2)} USD`)

export function fmtPrice(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return 'sin dato'
  const abs = Math.abs(n)
  const digits = abs >= 1000 ? 0 : abs >= 100 ? 1 : abs >= 10 ? 2 : abs >= 1 ? 3 : 4
  return new Intl.NumberFormat('es-ES', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(n)
}

export function fmtVolume(n: number | null | undefined): string {
  if (n == null) return '—'
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)} mil M`
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)} M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)} k`
  return n.toFixed(0)
}

export function parseDate(s: string | null | undefined): Date | null {
  if (!s) return null
  const d = new Date(s.includes('T') && !/[zZ]|[+-]\d\d:?\d\d$/.test(s) ? `${s}Z` : s)
  return Number.isNaN(d.getTime()) ? null : d
}

const dtShort = new Intl.DateTimeFormat('es-ES', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
const dtDate = new Intl.DateTimeFormat('es-ES', { day: '2-digit', month: 'short', year: 'numeric' })
const dtTime = new Intl.DateTimeFormat('es-ES', { hour: '2-digit', minute: '2-digit' })
const dtLong = new Intl.DateTimeFormat('es-ES', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })

export const fmtDateTime = (s: string | null | undefined): string => {
  const d = parseDate(s)
  return d ? dtShort.format(d) : '—'
}
export const fmtDate = (s: string | null | undefined): string => {
  const d = parseDate(s)
  return d ? dtDate.format(d) : '—'
}
export const fmtTime = (s: string | null | undefined): string => {
  const d = parseDate(s)
  return d ? dtTime.format(d) : '—'
}
export const fmtLongDate = (s: string | null | undefined): string => {
  const d = parseDate(s)
  return d ? dtLong.format(d) : '—'
}

export function fmtAgo(s: string | null | undefined, now = Date.now()): string {
  const d = parseDate(s)
  if (!d) return '—'
  const diff = Math.max(0, now - d.getTime())
  const m = Math.floor(diff / 60000)
  if (m < 1) return 'ahora'
  if (m < 60) return `hace ${m} min`
  const h = Math.floor(m / 60)
  if (h < 48) return `hace ${h} h`
  const days = Math.floor(h / 24)
  if (days < 60) return `hace ${days} d`
  return dtDate.format(d)
}

export const hoursSince = (s: string | null | undefined, now = Date.now()): number | null => {
  const d = parseDate(s)
  return d ? (now - d.getTime()) / 3600000 : null
}

export const clamp = (v: number, lo: number, hi: number): number => Math.min(hi, Math.max(lo, v))

/** Color de la escala secuencial (amarillo → negro) para t ∈ [0,1], expresado con tokens CSS. */
export const seqColor = (t: number): string => `color-mix(in oklab, var(--c-seq-hi) ${Math.round(clamp(t, 0, 1) * 100)}%, var(--c-seq-lo))`

export const isoDateLocal = (d = new Date()): string => {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

export const plural = (n: number, one: string, many: string): string => `${fmtInt(n)} ${n === 1 ? one : many}`
