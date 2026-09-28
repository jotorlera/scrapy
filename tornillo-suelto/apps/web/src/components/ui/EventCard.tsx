import { useNavigate } from 'react-router-dom'
import type { EventSummary } from '../../api/types'
import { hoursSince } from '../../lib/format'
import { ideologyLabel, IDEOLOGY_ORDER } from '../../lib/labels'
import { CountryChips, DomainChip, ProvenanceChip } from './basics'
import { MaterialityBar } from './MaterialityBar'

/** Reparto por ecosistema ideológico en una barra apilada de un solo tono. */
export function EcosystemBar({ ecosystems, width }: { ecosystems: Record<string, number>; width?: number }) {
  const keys = IDEOLOGY_ORDER.filter((k) => ecosystems[k]).concat(Object.keys(ecosystems).filter((k) => !IDEOLOGY_ORDER.includes(k)))
  const total = keys.reduce((s, k) => s + ecosystems[k], 0)
  if (!total) return null
  const n = keys.length
  return (
    <span className="ecobar" style={width ? { width } : undefined} title={keys.map((k) => `${ideologyLabel(k)}: ${ecosystems[k]}`).join(' · ')}>
      {keys.map((k, i) => (
        <i key={k} style={{ width: `${(ecosystems[k] / total) * 100}%`, background: `color-mix(in oklab, var(--c-seq-hi) ${Math.round((i / Math.max(1, n - 1)) * 85 + 5)}%, var(--c-seq-lo))`, borderRight: '1px solid var(--c-bg)' }} />
      ))}
    </span>
  )
}

export function EventCard({ event, hasQuestion = false, showProvenance = false, onSelect }: { event: EventSummary; hasQuestion?: boolean; showProvenance?: boolean; onSelect?: (e: EventSummary) => void }) {
  const nav = useNavigate()
  const isNew = (hoursSince(event.first_seen_at) ?? 99) < 24
  const open = () => {
    onSelect?.(event)
    nav(`/eventos/${event.id}`)
  }
  return (
    <article
      className="event-card"
      data-nav-item=""
      tabIndex={0}
      onClick={open}
      onKeyDown={(e) => {
        if (e.key === 'Enter' && e.target === e.currentTarget) open()
      }}
    >
      <div className="title">{event.title_neutral}</div>
      <div className="meta">
        <MaterialityBar value={event.materiality} breakdown={event.materiality_breakdown} compact />
        <CountryChips countries={event.countries} max={3} />
        <DomainChip domain={event.domain} />
        <span className="num" title="Fuentes">
          {event.n_sources} f.
        </span>
        {event.n_primary > 0 && (
          <span className="num" title="Fuentes primarias">
            {event.n_primary} prim.
          </span>
        )}
        {event.langs.length > 0 && <span className="mono">{event.langs.slice(0, 4).join(' ')}</span>}
        <span className="flags">
          {isNew && <span className="flag new">24 h</span>}
          {event.silences.length > 0 && (
            <span className="flag silence" title={`Silencio en ${event.silences.map((s) => s.ecosystem).join(', ')}`}>
              silencio
            </span>
          )}
          {hasQuestion && <span className="flag question">pregunta abierta</span>}
        </span>
        {showProvenance && <ProvenanceChip titleSource={event.title_source} />}
      </div>
      <EcosystemBar ecosystems={event.ecosystems} width={120} />
    </article>
  )
}
