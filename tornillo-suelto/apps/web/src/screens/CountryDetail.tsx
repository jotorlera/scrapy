import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { CountrySheet } from '../api/types'
import { AgentStream } from '../components/ui/AgentStream'
import { Card, EmptyState, ErrorBox, ExtLink, Loading } from '../components/ui/basics'
import { EventCard } from '../components/ui/EventCard'
import { fmtDateTime, fmtInt, fmtPct } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { blocLabel, dimensionLabel } from '../lib/labels'
import { useStore } from '../state/store'
import './screens.css'

export default function CountryDetail() {
  const { iso2 = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const days = Number(params.get('dias') ?? 7)
  const { setCurrentEvent, agentsEnabled, agents } = useStore()
  const [showChanged, setShowChanged] = useState(false)
  const [streamKey, setStreamKey] = useState(0)
  const { data, error, loading } = useAsync<CountrySheet>(() => api.country(iso2, days), [iso2, days])
  useEffect(() => setShowChanged(false), [iso2])

  if (loading && !data) return <Loading text="Cargando ficha…" />
  if (error) return <ErrorBox error={error} />
  if (!data) return null
  const c = data.country
  const cov = data.coverage
  const covTotal = Math.max(1, cov.local + cov.foreign)
  const blocMax = Math.max(1, ...Object.values(cov.by_bloc))

  return (
    <div>
      <div className="screen-head">
        <div>
          <div className="row wrap small">
            <Link to="/paises">← Países</Link>
            <span className="chip dark">nivel {c.level}</span>
            <span className="chip">{blocLabel(c.bloc)}</span>
            <span className="muted mono">{c.iso2}</span>
          </div>
          <h1>{c.name}</h1>
          <div className="sub">{c.name_en} · lat {c.lat}, lon {c.lon}</div>
        </div>
        <div className="tools">
          <div className="seg" role="group" aria-label="Ventana">
            {[1, 7, 30].map((d) => (
              <button key={d} type="button" aria-pressed={days === d} onClick={() => setParams({ dias: String(d) }, { replace: true })}>
                {d === 1 ? '24 h' : `${d} d`}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setShowChanged(true)
              setStreamKey((k) => k + 1)
            }}
          >
            ¿Qué ha cambiado?
          </button>
        </div>
      </div>

      <section className="section" style={{ marginTop: 0 }}>
        <div className="section-head">
          <h2>Variables de estado</h2>
          <span className="muted small">último valor y umbral de alerta</span>
        </div>
        {data.variables.length === 0 && <p className="muted small">Sin variables de estado definidas para este país (solo los de nivel A las tienen).</p>}
        <div className="stat-tiles">
          {data.variables.map((v) => (
            <div key={v.id} className="stat-tile" title={v.source_hint ?? undefined}>
              <div className="k">
                {dimensionLabel(v.dimension)} · {v.key}
              </div>
              <div className="v">{v.last_value == null ? <span className="muted" style={{ fontSize: 13 }}>sin dato</span> : `${fmtInt(v.last_value)}${v.unit ? ` ${v.unit}` : ''}`}</div>
              <div className="k">
                umbral {String(v.threshold.type ?? '')} {String(v.threshold.value ?? '')} {v.unit ?? ''} {v.last_at ? `· ${fmtDateTime(v.last_at)}` : ''}
              </div>
            </div>
          ))}
        </div>
      </section>

      {showChanged && (
        <section className="section">
          <div className="section-head">
            <h2>Qué ha cambiado en {days === 1 ? '24 h' : `${days} días`}</h2>
            <span className="muted small">{data.what_changed.length} cambios materiales (materialidad ≥ 40 o irreversibilidad ≥ 0,6)</span>
          </div>
          {data.what_changed.length === 0 && <p className="muted">Nada material en la ventana. Amplía a 30 días.</p>}
          <div className="two-col narrow-right">
            <div>
              {data.what_changed.map((e) => (
                <EventCard key={e.id} event={e} onSelect={setCurrentEvent} />
              ))}
            </div>
            <div>
              {agentsEnabled ? (
                <AgentStream title={`Narrativa del cambio · ${c.name}`} url={`/api/agents/country_changes/${iso2}?days=${days}`} runKey={`${iso2}-${days}-${streamKey}`} />
              ) : (
                <div className="notice warn">{agents?.message ?? 'Agentes desactivados: añade ANTHROPIC_API_KEY en .env.'} La lista de la izquierda es determinista y siempre está disponible.</div>
              )}
            </div>
          </div>
        </section>
      )}

      <div className="two-col narrow-right">
        <section className="section">
          <div className="section-head">
            <h2>Eventos</h2>
            <span className="muted small">{data.events.length} en {days === 1 ? '24 h' : `${days} d`}</span>
          </div>
          {data.events.length === 0 && <EmptyState title="Sin eventos">Ningún evento menciona a {c.name} en la ventana.</EmptyState>}
          {data.events.map((e) => (
            <EventCard key={e.id} event={e} onSelect={setCurrentEvent} />
          ))}
        </section>
        <div className="col" style={{ gap: 'var(--sp-4)' }}>
          <section className="section">
            <h2>miniPRISMA</h2>
            <p className="muted small">Prensa nacional frente a extranjera sobre los eventos del país.</p>
            <div className="hbars">
              <span>Local</span>
              <span className="bar accent">
                <i style={{ width: `${(cov.local / covTotal) * 100}%` }} />
              </span>
              <span className="num">
                {cov.local} ({fmtPct(cov.local / covTotal)})
              </span>
              <span>Extranjera</span>
              <span className="bar">
                <i style={{ width: `${(cov.foreign / covTotal) * 100}%` }} />
              </span>
              <span className="num">
                {cov.foreign} ({fmtPct(cov.foreign / covTotal)})
              </span>
            </div>
            <div className="label" style={{ margin: '10px 0 4px' }}>
              Por bloque
            </div>
            <div className="hbars">
              {Object.entries(cov.by_bloc)
                .sort((a, b) => b[1] - a[1])
                .map(([b, n]) => (
                  <div key={b} style={{ display: 'contents' }}>
                    <span>{blocLabel(b)}</span>
                    <span className="bar">
                      <i style={{ width: `${(n / blocMax) * 100}%` }} />
                    </span>
                    <span className="num">{n}</span>
                  </div>
                ))}
            </div>
          </section>
          <section className="section">
            <h2>Deltas</h2>
            {data.deltas.length === 0 && <p className="muted small">Sin deltas registrados.</p>}
            {data.deltas.map((d) => (
              <div key={d.id} className="delta">
                <div className="head">
                  <span className="chip">{dimensionLabel(d.dimension)}</span>
                  <span className="muted small mono">{fmtDateTime(d.detected_at)}</span>
                </div>
                <div>{d.description}</div>
                {d.event_id && (
                  <div className="src">
                    <Link to={`/eventos/${d.event_id}`}>{d.event_title ?? 'evento'}</Link>
                  </div>
                )}
              </div>
            ))}
          </section>
          <section className="section">
            <h2>Preguntas abiertas</h2>
            {data.questions.length === 0 && (
              <p className="muted small">
                Sin preguntas de pronóstico sobre {c.name}. <Link to={`/pronosticos?nuevo=1&pais=${iso2}`}>Crear una</Link>.
              </p>
            )}
            {data.questions.map((q) => (
              <Card key={q.id} className="flat" style={{ marginBottom: 6 }}>
                <Link to={`/pronosticos/${q.id}`}>{q.title}</Link>
                <div className="muted small">cierra {fmtDateTime(q.close_at)}</div>
              </Card>
            ))}
          </section>
          <p className="muted small">
            Coordenadas y nombres del gazetteer local. <ExtLink href={`https://www.wikidata.org/w/index.php?search=${encodeURIComponent(c.name_en)}`}>Wikidata ↗</ExtLink>
          </p>
        </div>
      </div>
    </div>
  )
}
