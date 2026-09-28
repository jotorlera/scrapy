import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { CountryRow, EventSummary } from '../api/types'
import { EmptyState, ErrorBox, Loading } from '../components/ui/basics'
import { EventCard } from '../components/ui/EventCard'
import { useAsync, useDebounced } from '../lib/hooks'
import { domainLabel, DOMAINS } from '../lib/labels'
import { useStore } from '../state/store'
import './screens.css'

export default function EventsList() {
  const [params, setParams] = useSearchParams()
  const hours = Number(params.get('h') ?? 168)
  const domain = params.get('dominio') ?? ''
  const country = params.get('pais') ?? ''
  const [q, setQ] = useState(params.get('q') ?? '')
  const dq = useDebounced(q, 250)
  const { setCurrentEvent } = useStore()
  const [countries, setCountries] = useState<CountryRow[]>([])
  useEffect(() => {
    api.countries().then((r) => setCountries(r.countries)).catch(() => undefined)
  }, [])

  const set = (k: string, v: string) => {
    const p = new URLSearchParams(params)
    if (v) p.set(k, v)
    else p.delete(k)
    setParams(p, { replace: true })
  }
  useEffect(() => set('q', dq), [dq]) // eslint-disable-line react-hooks/exhaustive-deps

  const { data, error, loading } = useAsync<{ events: EventSummary[] }>(() => api.events({ hours, limit: 150, q: dq || undefined, domain: domain || undefined, country: country || undefined }), [hours, dq, domain, country])

  return (
    <div>
      <div className="screen-head">
        <div>
          <h1>Eventos</h1>
          <div className="sub">Acontecimientos agrupados por el motor, ordenados por materialidad. Cada uno lleva sus afirmaciones con cita.</div>
        </div>
      </div>
      <div className="filters">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar en el título…" aria-label="Buscar eventos" />
        <div className="seg" role="group" aria-label="Ventana">
          {[24, 168, 720].map((h) => (
            <button key={h} type="button" aria-pressed={hours === h} onClick={() => set('h', String(h))}>
              {h === 24 ? '24 h' : h === 168 ? '7 d' : '30 d'}
            </button>
          ))}
        </div>
        <select value={domain} onChange={(e) => set('dominio', e.target.value)} aria-label="Dominio">
          <option value="">Todos los dominios</option>
          {DOMAINS.map((d) => (
            <option key={d} value={d}>
              {domainLabel(d)}
            </option>
          ))}
        </select>
        <select value={country} onChange={(e) => set('pais', e.target.value)} aria-label="País">
          <option value="">Todos los países</option>
          {countries.map((c) => (
            <option key={c.iso2} value={c.iso2}>
              {c.name} ({c.iso2})
            </option>
          ))}
        </select>
        {data && <span className="muted small">{data.events.length} eventos</span>}
      </div>
      {loading && !data && <Loading />}
      <ErrorBox error={error} />
      {data && data.events.length === 0 && <EmptyState title="Sin eventos">Prueba a ampliar la ventana temporal o a quitar filtros.</EmptyState>}
      <div style={{ maxWidth: 900 }}>
        {data?.events.map((e) => (
          <EventCard key={e.id} event={e} showProvenance onSelect={setCurrentEvent} />
        ))}
      </div>
    </div>
  )
}
