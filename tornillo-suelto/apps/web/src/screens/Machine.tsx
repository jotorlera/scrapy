import { useEffect, useMemo, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { MachineResponse, MachineSource } from '../api/types'
import { Card, ErrorBox, Loading } from '../components/ui/basics'
import { DataTable } from '../components/ui/DataTable'
import { fmtAgo, fmtDateTime, fmtInt, fmtUsd } from '../lib/format'
import { useAsync, useInterval } from '../lib/hooks'
import { sourceTypeLabel } from '../lib/labels'
import { useStore } from '../state/store'
import './screens.css'

export default function Machine() {
  const { data, error, loading, reload } = useAsync<MachineResponse>(() => api.machine(), [])
  const { toast, refreshAgents } = useStore()
  const [running, setRunning] = useState<Record<string, boolean>>({})
  const [filter, setFilter] = useState('')
  const [onlyProblems, setOnlyProblems] = useState(false)
  const anyRunning = Object.values(running).some(Boolean)
  const pollRunning = () => api.machineRunning().then(setRunning).catch(() => undefined)
  useEffect(() => {
    void pollRunning()
  }, [])
  useInterval(() => {
    void pollRunning()
    if (anyRunning) reload()
  }, anyRunning ? 5000 : 30000)

  const act = async (label: string, fn: () => Promise<{ started?: boolean; reason?: string } | Record<string, unknown>>) => {
    try {
      const r = await fn()
      if ('started' in r && r.started === false) toast(String(r.reason ?? 'No se pudo lanzar'), 'warn')
      else toast(`${label} en marcha`)
      void pollRunning()
      reload()
      refreshAgents()
    } catch (e) {
      toast(e instanceof ApiError ? e.userMessage : String(e), 'warn')
    }
  }

  const sources = useMemo(() => {
    const f = filter.toLowerCase()
    return (data?.sources ?? []).filter((s) => (!f || s.name.toLowerCase().includes(f) || s.slug.includes(f) || (s.country ?? '').toLowerCase() === f) && (!onlyProblems || s.last_error || (s.active && s.feeds.length && !s.last_ok_at)))
  }, [data, filter, onlyProblems])

  const budget = data?.budget
  const t = data?.totals ?? {}
  return (
    <div>
      <div className="screen-head">
        <div>
          <h1>Sala de máquinas</h1>
          <div className="sub">Salud de los conectores, jobs, presupuesto y coste de los modelos. Embedder: {data?.embedder ?? '…'}</div>
        </div>
        <div className="tools">
          <button type="button" className="btn btn-primary" onClick={() => act('Ingesta', () => api.ingest(false))} disabled={!!running.ingest}>
            {running.ingest ? 'Ingestando…' : 'Ingestar ahora'}
          </button>
          <button type="button" className="btn" onClick={() => act('Actualización de mercados', () => api.refreshMarkets())} disabled={!!running.markets}>
            {running.markets ? 'Actualizando…' : 'Actualizar mercados'}
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => act('Recálculo', () => api.recompute(72))}>
            Recalcular (72 h)
          </button>
          {anyRunning && <span className="loading">job en curso · sondeo cada 5 s</span>}
        </div>
      </div>
      {loading && !data && <Loading />}
      <ErrorBox error={error} retry={reload} />
      {data && (
        <>
          <div className="stat-tiles" style={{ marginBottom: 12 }}>
            {[
              ['fuentes activas', `${t.sources_active}/${t.sources_total}`],
              ['con feed', t.sources_with_feed],
              ['OK hoy', t.sources_ok_24h],
              ['documentos', fmtInt(t.documents)],
              ['docs 24 h', fmtInt(t.documents_24h)],
              ['eventos', fmtInt(t.events)],
              ['afirmaciones', fmtInt(t.claims)],
              ['confirmadas', fmtInt(t.claims_confirmed)],
              ['BD (MB)', t.db_size_mb],
            ].map(([k, v]) => (
              <div key={String(k)} className="stat-tile">
                <div className="v">{String(v)}</div>
                <div className="k">{k}</div>
              </div>
            ))}
          </div>

          {budget && (
            <Card title="Presupuesto LLM (hoy)" extra={<span className="muted small">{budget.enabled ? 'agentes activos' : 'sin clave: gasto 0'}</span>}>
              <div className="row" style={{ gap: 12 }}>
                <span className="bar" style={{ flex: 1, height: 10 }}>
                  <i style={{ width: `${Math.min(100, budget.fraction * 100)}%`, background: budget.hard_stop ? 'var(--c-warn)' : budget.pause_noncritical ? 'var(--c-disputed)' : 'var(--c-accent)' }} />
                </span>
                <span className="num">
                  {fmtUsd(budget.spent_today_usd)} / {fmtUsd(budget.daily_cap_usd)} ({Math.round(budget.fraction * 100)} %)
                </span>
              </div>
              {budget.pause_noncritical && !budget.hard_stop && <div className="notice warn" style={{ marginTop: 6 }}>80 % del tope: las tareas no críticas están en pausa; sigue la ingesta y el brief.</div>}
              {budget.hard_stop && <div className="notice warn" style={{ marginTop: 6 }}>Tope diario alcanzado: solo continúa la ingesta sin modelo.</div>}
              <div className="row wrap small muted" style={{ marginTop: 6 }}>
                <span>Reparto:</span>
                {Object.entries(budget.allocation).map(([k, v]) => (
                  <span key={k}>
                    {k.replace(/_/g, ' ')} {Math.round(v * 100)} %
                  </span>
                ))}
              </div>
            </Card>
          )}

          <section className="section">
            <div className="section-head">
              <h2>Fuentes</h2>
              <span className="row">
                <input type="search" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filtrar…" aria-label="Filtrar fuentes" />
                <label className="row small">
                  <input type="checkbox" checked={onlyProblems} onChange={(e) => setOnlyProblems(e.target.checked)} /> solo con problemas
                </label>
                <span className="muted small">{sources.length}</span>
              </span>
            </div>
            <DataTable<MachineSource>
              rows={sources}
              rowKey={(s) => s.id}
              maxHeight={420}
              initialSort={{ key: 'docs', dir: 'desc' }}
              columns={[
                { key: 'name', label: 'Fuente', render: (s) => <span title={s.slug}>{s.name}</span>, sort: (s) => s.name },
                { key: 'tier', label: 'Tier', num: true, render: (s) => s.tier, sort: (s) => s.tier, width: 50 },
                { key: 'type', label: 'Tipo', render: (s) => sourceTypeLabel(s.type), sort: (s) => s.type, width: 130 },
                { key: 'country', label: 'País', render: (s) => <span className="mono">{s.country ?? '—'}</span>, sort: (s) => s.country ?? '', width: 50 },
                { key: 'feed', label: 'Feed', render: (s) => (s.feeds.length ? <span title={s.feeds.join('\n')}>sí ({s.feeds.length})</span> : <span className="muted">no</span>), sort: (s) => s.feeds.length, width: 60 },
                { key: 'ok', label: 'Último OK', render: (s) => (s.last_ok_at ? <span title={fmtDateTime(s.last_ok_at)}>{fmtAgo(s.last_ok_at)}</span> : <span className="muted">nunca</span>), sort: (s) => s.last_ok_at ?? '', width: 90 },
                { key: 'err', label: 'Error', render: (s) => (s.last_error ? <span className="warn small" title={s.last_error}>{s.last_error.slice(0, 60)}</span> : <span className="muted">—</span>), width: 220 },
                { key: 'docs', label: 'Docs 24 h', num: true, render: (s) => s.docs_24h, sort: (s) => s.docs_24h, width: 80 },
                {
                  key: 'toggle',
                  label: '',
                  width: 90,
                  render: (s) => (
                    <button
                      type="button"
                      className={`btn btn-sm ${s.active ? 'btn-ghost' : ''}`}
                      onClick={async (e) => {
                        e.stopPropagation()
                        await api.toggleSource(s.id)
                        reload()
                      }}
                    >
                      {s.active ? 'Desactivar' : 'Activar'}
                    </button>
                  ),
                },
              ]}
            />
          </section>

          <div className="two-col">
            <section className="section">
              <h2>Últimos jobs</h2>
              <table className="table">
                <thead>
                  <tr>
                    <th>Job</th>
                    <th>Inicio</th>
                    <th>Fin</th>
                    <th>OK</th>
                    <th>Stats</th>
                  </tr>
                </thead>
                <tbody>
                  {data.jobs.slice(0, 20).map((j) => (
                    <tr key={j.id}>
                      <td>{j.job}</td>
                      <td className="mono">{fmtDateTime(j.started_at)}</td>
                      <td className="mono">{j.finished_at ? fmtDateTime(j.finished_at) : <span className="loading" style={{ padding: 0 }}>en curso</span>}</td>
                      <td>{j.ok == null ? '…' : j.ok ? 'sí' : <span className="warn">no</span>}</td>
                      <td className="small mono" style={{ maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={JSON.stringify(j.stats)}>
                        {j.error ? <span className="warn">{j.error}</span> : JSON.stringify(j.stats)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
            <section className="section">
              <h2>Coste LLM por día, módulo y modelo</h2>
              {data.llm_cost.length === 0 && <p className="muted small">Sin llamadas registradas: los agentes están desactivados o no se han usado.</p>}
              {data.llm_cost.length > 0 && (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Día</th>
                      <th>Módulo</th>
                      <th>Modelo</th>
                      <th className="num">Llamadas</th>
                      <th className="num">Tokens in/out</th>
                      <th className="num">Caché</th>
                      <th className="num">Coste</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.llm_cost.map((c, i) => (
                      <tr key={i}>
                        <td className="mono">{c.day}</td>
                        <td>{c.module}</td>
                        <td className="mono small">{c.model}</td>
                        <td className="num">{c.n}</td>
                        <td className="num">
                          {fmtInt(c.input_tokens)}/{fmtInt(c.output_tokens)}
                        </td>
                        <td className="num">{fmtInt(c.cache_read)}</td>
                        <td className="num">{fmtUsd(c.cost)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <h3 style={{ margin: '12px 0 4px' }}>Últimas llamadas</h3>
              {data.llm_recent.length === 0 && <p className="muted small">Ninguna.</p>}
              {data.llm_recent.length > 0 && (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Hora</th>
                      <th>Agente</th>
                      <th>Modelo</th>
                      <th className="num">ms</th>
                      <th className="num">Coste</th>
                      <th>OK</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.llm_recent.map((c) => (
                      <tr key={c.id}>
                        <td className="mono">{fmtDateTime(c.at)}</td>
                        <td>
                          {c.module} · {c.agent}
                        </td>
                        <td className="mono small">{c.model}</td>
                        <td className="num">{c.latency_ms}</td>
                        <td className="num">{fmtUsd(c.cost_usd)}</td>
                        <td>{c.ok ? 'sí' : <span className="warn" title={c.error ?? ''}>no</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  )
}
