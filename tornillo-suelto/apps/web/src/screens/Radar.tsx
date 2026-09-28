import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { CountryRow, RadarResponse } from '../api/types'
import { WorldMap } from '../components/map/WorldMap'
import { EmptyState, ErrorBox, ExtLink, Loading } from '../components/ui/basics'
import { EventCard } from '../components/ui/EventCard'
import { fmtAgo, fmtInt } from '../lib/format'
import { useAsync, useInterval } from '../lib/hooks'
import { dimensionLabel, domainLabel, DOMAINS } from '../lib/labels'
import { useStore } from '../state/store'
import './screens.css'

const WINDOWS: Array<{ label: string; hours: number }> = [
  { label: '6 h', hours: 6 },
  { label: '24 h', hours: 24 },
  { label: '7 d', hours: 168 },
  { label: '30 d', hours: 720 },
]

export default function Radar() {
  const [params, setParams] = useSearchParams()
  const hours = Number(params.get('h') ?? 168)
  const domain = params.get('dominio') ?? ''
  const country = params.get('pais') ?? ''
  const { setCurrentEvent } = useStore()
  const nav = useNavigate()
  const [countries, setCountries] = useState<CountryRow[]>([])

  const set = (k: string, v: string) => {
    const p = new URLSearchParams(params)
    if (v) p.set(k, v)
    else p.delete(k)
    setParams(p, { replace: true })
  }

  const { data, error, loading, reload } = useAsync<RadarResponse>(() => api.radar({ hours, domain: domain || undefined, country: country || undefined, limit: 200 }), [hours, domain, country])
  useInterval(reload, 120000)
  useEffect(() => {
    api.countries().then((r) => setCountries(r.countries)).catch(() => undefined)
  }, [])

  const top15 = useMemo(() => (data?.events ?? []).slice(0, 15), [data])
  const totalDocs = data?.counts.documents ?? 0

  return (
    <div className="radar">
      <div className="radar-bar">
        <h1>Radar</h1>
        <div className="seg" role="group" aria-label="Ventana temporal">
          {WINDOWS.map((w) => (
            <button key={w.hours} type="button" aria-pressed={hours === w.hours} onClick={() => set('h', String(w.hours))}>
              {w.label}
            </button>
          ))}
        </div>
        <select value={domain} onChange={(e) => set('dominio', e.target.value)} aria-label="Dominio">
          <option value="">Todos los dominios</option>
          {DOMAINS.map((d) => (
            <option key={d} value={d}>
              {domainLabel(d)}
              {data?.by_domain[d] ? ` (${data.by_domain[d]})` : ''}
            </option>
          ))}
        </select>
        <select value={country} onChange={(e) => set('pais', e.target.value)} aria-label="País">
          <option value="">Todos los países</option>
          {countries.map((c) => (
            <option key={c.iso2} value={c.iso2}>
              {c.name} ({c.iso2}){c.events_7d ? ` · ${c.events_7d}` : ''}
            </option>
          ))}
        </select>
        {data && (
          <span className="muted small mono" style={{ marginLeft: 'auto' }}>
            {fmtInt(data.counts.events)} eventos · {fmtInt(totalDocs)} documentos · {data.counts.sources_ok} fuentes OK 24 h
          </span>
        )}
      </div>

      <aside className="deltas" aria-label="Deltas de variables de estado">
        <div className="col-title">
          <span className="label">Deltas</span>
          <span className="muted small">{data?.deltas.length ?? 0}</span>
        </div>
        {loading && !data && <Loading />}
        {data && data.deltas.length === 0 && <div className="delta muted">Ninguna variable de estado ha cruzado su umbral en la ventana. Los deltas salen de documentos primarios y afirmaciones confirmadas.</div>}
        {data?.deltas.map((d) => (
          <div key={d.id} className="delta">
            <div className="head">
              <Link to={`/paises/${d.scope}`} className="chip mono">
                {d.scope}
              </Link>
              <span className="chip">{dimensionLabel(d.dimension)}</span>
              <span className="muted small mono" style={{ marginLeft: 'auto' }}>
                {fmtAgo(d.detected_at)}
              </span>
            </div>
            <div className="desc">{d.description ?? d.key}</div>
            <div className="src">
              {d.event_id ? <Link to={`/eventos/${d.event_id}`}>{d.event_title ?? 'evento'}</Link> : d.event_title}
              {d.source_url && (
                <>
                  {' · '}
                  <ExtLink href={d.source_url} title={d.source_title ?? undefined}>
                    fuente ↗
                  </ExtLink>
                </>
              )}
              {d.source_hint && <span> · {d.source_hint}</span>}
            </div>
          </div>
        ))}
      </aside>

      <section className="map-area">
        {error && <ErrorBox error={error} retry={reload} />}
        {data && data.counts.events === 0 && !loading && (
          <EmptyState
            title="Sin eventos en la ventana"
            actions={
              <>
                <Link className="btn" to="/maquinas">
                  Ir a la Sala de máquinas y lanzar la ingesta
                </Link>
                <button type="button" className="btn btn-ghost" onClick={() => set('h', '720')}>
                  Ampliar a 30 d
                </button>
              </>
            }
          >
            No hay eventos actualizados en las últimas {hours} h{domain || country ? ' con estos filtros' : ''}. Si la base está vacía, lanza «Ingestar ahora»; la primera pasada tarda unos minutos.
          </EmptyState>
        )}
        <WorldMap events={data?.events ?? []} countries={countries} highlightIso2={country || null} onEvent={(e) => {
            setCurrentEvent(e)
            nav(`/eventos/${e.id}`)
          }}
          minHeight={380}
        />
        {data && (
          <div className="row wrap small muted">
            <span>{data.events.filter((e) => e.geo).length} eventos con geolocalización de {data.events.length} cargados (máx. 200 por materialidad).</span>
            <span>Pasa el ratón por un punto para ver el evento; clic o Enter: abre. Clic en un país: ficha.</span>
          </div>
        )}
      </section>

      <aside className="top" aria-label="Eventos por materialidad">
        <div className="col-title">
          <span className="label">Top 15 por materialidad</span>
          <Link to={`/eventos?h=${hours}`} className="small">
            ver todos
          </Link>
        </div>
        {loading && !data && <Loading />}
        {top15.map((e) => (
          <EventCard key={e.id} event={e} onSelect={setCurrentEvent} />
        ))}
      </aside>
    </div>
  )
}
