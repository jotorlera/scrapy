import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { CalibrationResponse, EnsembleOutput, ForecastQuestion, PredictionMarket } from '../api/types'
import { Card, CountryChips, EmptyState, ErrorBox, ExtLink, InfoIcon, Loading, Tabs } from '../components/ui/basics'
import { Modal } from '../components/ui/Modal'
import { fmt2, fmtDateTime, fmtPct, parseDate } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { FORECASTER_LABEL } from '../lib/labels'
import { useStore } from '../state/store'
import './screens.css'

function barClass(f: string) {
  if (f === 'user') return 'user'
  if (f.startsWith('market')) return 'market'
  return 'system'
}

/** Barras comparables: usuario · sistema (atlas_final o tasa base) · mercado. La del sistema se oculta hasta que el usuario pronostica. */
function ProbBars({ q, revealSystem }: { q: ForecastQuestion; revealSystem: boolean }) {
  const entries = Object.entries(q.latest)
  const userHas = 'user' in q.latest
  const show = revealSystem || userHas || q.status === 'resolved'
  const order = ['user', 'atlas_final', 'base_rate']
  // Tasa base declarada al crear la pregunta (si aún no hay un pronóstico `base_rate` registrado)
  if (q.base_rate != null && !('base_rate' in q.latest)) entries.push(['base_rate', { p: q.base_rate, at: q.open_at, rationale: q.base_rate_note ?? 'tasa base declarada' }])
  const sorted = entries.sort((a, b) => {
    const ia = order.indexOf(a[0])
    const ib = order.indexOf(b[0])
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib)
  })
  return (
    <div className="pbars">
      {sorted.length === 0 && <span className="muted" style={{ gridColumn: '1 / -1' }}>Sin pronósticos todavía.</span>}
      {sorted.map(([f, v]) => {
        const hidden = !show && f !== 'user' && !f.startsWith('market')
        return (
          <div key={f} style={{ display: 'contents' }}>
            <span title={v.rationale ?? undefined}>{FORECASTER_LABEL(f)}</span>
            {hidden ? (
              <span className="hidden-p">haz tu pronóstico para verla</span>
            ) : (
              <span className={`bar ${barClass(f)}`}>
                <i style={{ width: `${v.p * 100}%` }} />
              </span>
            )}
            <span className="num right">{hidden ? '··' : fmtPct(v.p)}</span>
          </div>
        )
      })}
      {q.market && !('market:' + q.market.venue in q.latest) && (
        <div style={{ display: 'contents' }}>
          <span>Mercado ({q.market.venue})</span>
          <span className="bar market">
            <i style={{ width: `${(q.market.probability ?? 0) * 100}%` }} />
          </span>
          <span className="num right">{fmtPct(q.market.probability)}</span>
        </div>
      )}
    </div>
  )
}

function SeriesChart({ q }: { q: ForecastQuestion }) {
  const pts = q.series.filter((s) => parseDate(s.made_at))
  if (pts.length < 1) return <p className="muted small">Sin serie temporal todavía.</p>
  const t0 = Math.min(...pts.map((p) => parseDate(p.made_at)!.getTime()), parseDate(q.open_at)?.getTime() ?? Infinity)
  const t1 = Math.max(...pts.map((p) => parseDate(p.made_at)!.getTime()), Math.min(Date.now(), parseDate(q.close_at)?.getTime() ?? Date.now()))
  const w = 560
  const h = 140
  const x = (t: number) => 30 + ((t - t0) / Math.max(1, t1 - t0)) * (w - 40)
  const y = (p: number) => 10 + (1 - p) * (h - 30)
  const byF = new Map<string, typeof pts>()
  for (const p of pts) byF.set(p.forecaster, [...(byF.get(p.forecaster) ?? []), p])
  const colors: Record<string, string> = { user: 'var(--c-accent)', system: 'var(--c-black)', market: 'var(--c-link)' }
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="graph-svg" role="img" aria-label="Evolución de los pronósticos">
      {[0, 0.25, 0.5, 0.75, 1].map((p) => (
        <g key={p}>
          <line x1={30} x2={w - 10} y1={y(p)} y2={y(p)} stroke="var(--c-line)" />
          <text x={2} y={y(p) + 3} fontSize="9" fill="var(--c-muted)" fontFamily="var(--font-mono)">
            {Math.round(p * 100)}
          </text>
        </g>
      ))}
      {Array.from(byF.entries()).map(([f, ps]) => {
        const c = colors[barClass(f)]
        const sorted = ps.slice().sort((a, b) => parseDate(a.made_at)!.getTime() - parseDate(b.made_at)!.getTime())
        const d = sorted.map((p, i) => `${i ? 'L' : 'M'}${x(parseDate(p.made_at)!.getTime()).toFixed(1)},${y(p.probability).toFixed(1)}`).join(' ')
        return (
          <g key={f}>
            <path d={d} fill="none" stroke={c} strokeWidth={f === 'user' ? 2.2 : 1.4} strokeDasharray={f.startsWith('agent') ? '3 3' : undefined} />
            {sorted.map((p, i) => (
              <circle key={i} cx={x(parseDate(p.made_at)!.getTime())} cy={y(p.probability)} r={3} fill={c} stroke="var(--c-bg)">
                <title>
                  {FORECASTER_LABEL(f)} · {fmtPct(p.probability)} · {fmtDateTime(p.made_at)}
                  {p.rationale ? ` · ${p.rationale}` : ''}
                </title>
              </circle>
            ))}
          </g>
        )
      })}
      <text x={30} y={h - 2} fontSize="9" fill="var(--c-muted)" fontFamily="var(--font-mono)">
        {fmtDateTime(new Date(t0).toISOString())}
      </text>
      <text x={w - 10} y={h - 2} fontSize="9" fill="var(--c-muted)" fontFamily="var(--font-mono)" textAnchor="end">
        {fmtDateTime(new Date(t1).toISOString())}
      </text>
    </svg>
  )
}

function CalibrationPanel() {
  const { data, error, loading } = useAsync<CalibrationResponse>(() => api.calibration('user'), [])
  if (loading) return <Loading />
  if (error) {
    const e = error as ApiError
    return (
      <div className="errorbox">
        <b>Calibración no disponible.</b> {e.userMessage}
        {e.status === 404 && <div className="muted small">La API responde 404 «pregunta no encontrada»: la ruta /forecasts/calibration está declarada después de /forecasts/{'{qid}'} en routes_thinker.py y queda tapada. Basta con mover la función `calibration` antes de `get_question`.</div>}
      </div>
    )
  }
  if (!data) return null
  const cal = data.calibration
  const w = 300
  const h = 300
  const x = (p: number) => 30 + p * (w - 40)
  const y = (p: number) => 10 + (1 - p) * (h - 40)
  return (
    <div className="col">
      <div className="row wrap">
        <div className="stat-tile">
          <div className="v">{cal.n}</div>
          <div className="k">resueltas</div>
        </div>
        <div className="stat-tile">
          <div className="v">{cal.brier == null ? '—' : fmt2(cal.brier)}</div>
          <div className="k">Brier</div>
        </div>
        <div className="stat-tile">
          <div className="v">{cal.reliability == null ? '—' : cal.reliability.toFixed(3)}</div>
          <div className="k">fiabilidad</div>
        </div>
        <div className="stat-tile">
          <div className="v">{cal.resolution == null ? '—' : cal.resolution.toFixed(3)}</div>
          <div className="k">resolución</div>
        </div>
        <div className="stat-tile">
          <div className="v">{cal.uncertainty == null ? '—' : cal.uncertainty.toFixed(3)}</div>
          <div className="k">incertidumbre</div>
        </div>
      </div>
      {cal.n === 0 ? (
        <p className="muted small">Sin preguntas resueltas con pronóstico tuyo: la curva aparece cuando resuelvas la primera.</p>
      ) : (
        <svg viewBox={`0 0 ${w} ${h}`} className="graph-svg" style={{ maxWidth: 360 }} role="img" aria-label="Curva de calibración">
          <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} stroke="var(--c-line)" strokeDasharray="4 3" />
          {[0, 0.5, 1].map((p) => (
            <g key={p}>
              <text x={x(p)} y={h - 8} fontSize="9" textAnchor="middle" fill="var(--c-muted)" fontFamily="var(--font-mono)">
                {Math.round(p * 100)}
              </text>
              <text x={4} y={y(p) + 3} fontSize="9" fill="var(--c-muted)" fontFamily="var(--font-mono)">
                {Math.round(p * 100)}
              </text>
            </g>
          ))}
          {cal.bins
            .filter((b) => b.n > 0 && b.mean_p != null && b.freq != null)
            .map((b, i) => (
              <g key={i}>
                {b.ci && <line x1={x(b.mean_p!)} x2={x(b.mean_p!)} y1={y(b.ci[0])} y2={y(b.ci[1])} stroke="var(--c-muted)" />}
                <circle cx={x(b.mean_p!)} cy={y(b.freq!)} r={3 + Math.min(6, b.n)} fill="var(--c-accent)" stroke="var(--c-black)">
                  <title>
                    {Math.round(b.lo * 100)}–{Math.round(b.hi * 100)} %: media {fmtPct(b.mean_p)} · frecuencia {fmtPct(b.freq)} · n = {b.n} · IC Wilson {b.ci ? `${fmtPct(b.ci[0])}–${fmtPct(b.ci[1])}` : '—'}
                  </title>
                </circle>
              </g>
            ))}
          <text x={w / 2} y={h - 22} fontSize="9" textAnchor="middle" fill="var(--c-muted)">
            probabilidad media pronosticada
          </text>
        </svg>
      )}
      <div className="label">Resumen por pronosticador</div>
      <table className="table">
        <thead>
          <tr>
            <th>Pronosticador</th>
            <th className="num">n</th>
            <th className="num">Brier</th>
            <th className="num">Log score</th>
            <th className="num">BSS vs. tasa base</th>
          </tr>
        </thead>
        <tbody>
          {data.summary.length === 0 && (
            <tr>
              <td colSpan={5} className="muted">
                Sin puntuaciones: resuelve preguntas para compararte con ATLAS, la tasa base y los mercados.
              </td>
            </tr>
          )}
          {data.summary.map((s) => (
            <tr key={s.forecaster}>
              <td>{FORECASTER_LABEL(s.forecaster)}</td>
              <td className="num">{s.n}</td>
              <td className="num">{s.brier?.toFixed(3)}</td>
              <td className="num">{s.log_score?.toFixed(3)}</td>
              <td className="num">{s.bss_vs_base_rate == null ? '—' : s.bss_vs_base_rate.toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function NewQuestionForm({ eventId, country, onCreated, onCancel }: { eventId: string | null; country: string | null; onCreated: (id: string) => void; onCancel: () => void }) {
  const [f, setF] = useState({ title: '', resolution_criteria: '', resolution_source: '', close_at: '', resolve_by: '', domain: '', countries: country ?? '', base_rate: '', base_rate_note: '' })
  const [issues, setIssues] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const submit = async () => {
    setBusy(true)
    setIssues([])
    try {
      const r = await api.createQuestion({
        title: f.title,
        resolution_criteria: f.resolution_criteria,
        resolution_source: f.resolution_source || null,
        close_at: f.close_at ? new Date(f.close_at).toISOString() : '',
        resolve_by: f.resolve_by ? new Date(f.resolve_by).toISOString() : null,
        origin_event_id: eventId,
        domain: f.domain || null,
        countries: f.countries
          .split(/[,\s]+/)
          .map((s) => s.trim().toUpperCase())
          .filter(Boolean),
        base_rate: f.base_rate ? Number(f.base_rate) / 100 : null,
        base_rate_note: f.base_rate_note || null,
      })
      onCreated(r.id)
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        const d = e.detail as { issues?: string[] } | Array<{ msg: string }>
        if (Array.isArray(d)) setIssues(d.map((x) => x.msg))
        else setIssues(d.issues ?? [e.userMessage])
      } else setIssues([e instanceof Error ? e.message : String(e)])
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="col">
      {eventId && <div className="notice">Pregunta originada en el evento {eventId.slice(0, 8)}…</div>}
      <label className="field">
        Pregunta cerrada (con «?»)
        <input type="text" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="¿Bajará el BCE el tipo de depósito en la reunión de diciembre de 2026?" />
      </label>
      <label className="field">
        Criterio de resolución (fuente, umbral y definición; ≥ 30 caracteres)
        <textarea rows={3} value={f.resolution_criteria} onChange={(e) => setF({ ...f, resolution_criteria: e.target.value })} />
      </label>
      <div className="two-col">
        <label className="field">
          Fuente de resolución
          <input type="text" value={f.resolution_source} onChange={(e) => setF({ ...f, resolution_source: e.target.value })} />
        </label>
        <label className="field">
          Dominio
          <input type="text" value={f.domain} onChange={(e) => setF({ ...f, domain: e.target.value })} placeholder="economy, politics…" />
        </label>
        <label className="field">
          Cierre
          <input type="datetime-local" value={f.close_at} onChange={(e) => setF({ ...f, close_at: e.target.value })} />
        </label>
        <label className="field">
          Resolver antes de (opcional)
          <input type="datetime-local" value={f.resolve_by} onChange={(e) => setF({ ...f, resolve_by: e.target.value })} />
        </label>
        <label className="field">
          Países (ISO2, separados por comas)
          <input type="text" value={f.countries} onChange={(e) => setF({ ...f, countries: e.target.value })} />
        </label>
        <label className="field">
          Tasa base (%) · entre 3 y 97
          <input type="number" min={0} max={100} value={f.base_rate} onChange={(e) => setF({ ...f, base_rate: e.target.value })} />
        </label>
      </div>
      <label className="field">
        Nota de la tasa base (clase de referencia)
        <input type="text" value={f.base_rate_note} onChange={(e) => setF({ ...f, base_rate_note: e.target.value })} />
      </label>
      {issues.length > 0 && (
        <div className="errorbox">
          <b>El filtro de calidad rechaza la pregunta:</b>
          <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
            {issues.map((i, k) => (
              <li key={k}>{i}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="row" style={{ justifyContent: 'flex-end' }}>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Cancelar
        </button>
        <button type="button" className="btn btn-primary" onClick={submit} disabled={busy || !f.title || !f.resolution_criteria || !f.close_at}>
          Crear pregunta
        </button>
      </div>
    </div>
  )
}

function QuestionDetail({ id }: { id: string }) {
  const { data, error, loading, reload } = useAsync<ForecastQuestion>(() => api.forecast(id), [id])
  const { agentsEnabled, agents, toast } = useStore()
  const [p, setP] = useState(50)
  const [rationale, setRationale] = useState('')
  const [systemP, setSystemP] = useState<number | null | undefined>(undefined)
  const [markets, setMarkets] = useState<PredictionMarket[]>([])
  const [mq, setMq] = useState('')
  const [linkOpen, setLinkOpen] = useState(false)
  const [ensemble, setEnsemble] = useState<EnsembleOutput | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  useEffect(() => {
    if (linkOpen && !markets.length) api.markets().then((m) => setMarkets(m.prediction_markets)).catch(() => undefined)
  }, [linkOpen, markets.length])

  if (loading && !data) return <Loading />
  if (error) return <ErrorBox error={error} retry={reload} />
  if (!data) return null
  const q = data
  const userHas = 'user' in q.latest
  const submitForecast = async () => {
    setBusy('forecast')
    try {
      const r = await api.addForecast(id, p / 100, rationale || undefined)
      setSystemP(r.system_probability)
      toast(r.system_probability == null ? 'Pronóstico registrado. El sistema aún no tiene probabilidad para esta pregunta.' : `Pronóstico registrado. Sistema: ${fmtPct(r.system_probability)}`)
      reload()
    } catch (e) {
      toast(e instanceof ApiError ? e.userMessage : String(e), 'warn')
    } finally {
      setBusy(null)
    }
  }
  const resolve = async (outcome: 0 | 1) => {
    if (!window.confirm(`¿Resolver como ${outcome ? 'SÍ' : 'NO'}? Se calculan Brier y log score de todos los pronosticadores.`)) return
    const r = await api.resolveQuestion(id, outcome)
    toast(`Resuelta. Brier: ${Object.entries(r.scores).map(([f, s]) => `${FORECASTER_LABEL(f)} ${s.brier}`).join(' · ') || 'sin pronósticos'}`)
    reload()
  }
  const runEnsemble = async () => {
    setBusy('ensemble')
    try {
      const r = await api.ensemble(id)
      setEnsemble(r)
      reload()
    } catch (e) {
      toast(e instanceof ApiError ? e.userMessage : String(e), 'warn')
    } finally {
      setBusy(null)
    }
  }
  const filteredMarkets = markets.filter((m) => !mq || m.question.toLowerCase().includes(mq.toLowerCase())).slice(0, 40)

  return (
    <div>
      <div className="row small" style={{ marginBottom: 6 }}>
        <Link to="/pronosticos">← Pronósticos</Link>
        <span className="chip">{q.status === 'open' ? 'abierta' : 'resuelta'}</span>
        {q.domain && <span className="chip">{q.domain}</span>}
        <CountryChips countries={q.countries} />
        <span className="muted mono" style={{ marginLeft: 'auto' }}>
          abre {fmtDateTime(q.open_at)} · cierra {fmtDateTime(q.close_at)}
        </span>
      </div>
      <h1 style={{ fontSize: 24, marginBottom: 8 }}>{q.title}</h1>
      <div className="two-col narrow-right">
        <div className="col" style={{ gap: 'var(--sp-4)' }}>
          <Card title="Criterio de resolución">
            <p className="read">{q.resolution_criteria}</p>
            <div className="small muted">
              Fuente: {q.resolution_source ?? '—'} · resolver antes de {fmtDateTime(q.resolve_by)}
              {q.base_rate != null && (
                <>
                  {' '}
                  · tasa base {fmtPct(q.base_rate)} ({q.base_rate_note})
                </>
              )}
            </div>
            {q.origin_event && (
              <div className="small" style={{ marginTop: 4 }}>
                Origen: <Link to={`/eventos/${q.origin_event.id}`}>{q.origin_event.title_neutral}</Link>
              </div>
            )}
          </Card>
          <Card
            title={
              <>
                Probabilidades{' '}
                <InfoIcon label="Protocolo">
                  <h4>Protocolo anti-anclaje</h4>
                  <p>Introduces tu probabilidad antes de ver la del sistema (ATLAS o tasa base). Después se comparan y, al resolver, cada pronosticador recibe Brier y log score.</p>
                </InfoIcon>
              </>
            }
          >
            <ProbBars q={q} revealSystem={systemP !== undefined} />
            {systemP !== undefined && <div className="notice" style={{ marginTop: 8 }}>{systemP == null ? 'El sistema todavía no tiene probabilidad para esta pregunta (lanza el ensemble o declara una tasa base).' : `Probabilidad del sistema revelada: ${fmtPct(systemP)}.`}</div>}
          </Card>
          <Card title="Evolución">
            <SeriesChart q={q} />
          </Card>
          {q.scores.length > 0 && (
            <Card title="Puntuaciones">
              <table className="table">
                <thead>
                  <tr>
                    <th>Pronosticador</th>
                    <th className="num">Brier</th>
                    <th className="num">Log score</th>
                  </tr>
                </thead>
                <tbody>
                  {q.scores.map((s) => (
                    <tr key={s.forecaster}>
                      <td>{FORECASTER_LABEL(s.forecaster)}</td>
                      <td className="num">{s.brier}</td>
                      <td className="num">{s.log_score}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {q.outcome && (
                <div className="small muted">
                  Desenlace: {q.outcome.value ? 'SÍ' : 'NO'} {q.outcome.note ? `· ${q.outcome.note}` : ''} · {fmtDateTime(q.resolved_at)}
                </div>
              )}
            </Card>
          )}
          {ensemble && (
            <Card title="Ensemble ATLAS">
              {ensemble.error && <div className="errorbox">{ensemble.error}</div>}
              <table className="table">
                <tbody>
                  {ensemble.individual.map((i, k) => (
                    <tr key={k}>
                      <td>{i.approach}</td>
                      <td className="num">{i.probability == null ? (i.error ?? '—') : fmtPct(i.probability)}</td>
                      <td className="small muted">{i.output ? String((i.output as { reference_class?: string }).reference_class ?? '') : ''}</td>
                    </tr>
                  ))}
                  {ensemble.aggregate && (
                    <tr>
                      <td>
                        <strong>Agregado</strong>
                      </td>
                      <td className="num">
                        {fmtPct(ensemble.aggregate.raw)} → {fmtPct(ensemble.aggregate.extremized)}
                      </td>
                      <td className="small muted">extremización a = {ensemble.aggregate.a}</td>
                    </tr>
                  )}
                  {ensemble.final != null && (
                    <tr>
                      <td>
                        <strong>Final</strong>
                      </td>
                      <td className="num">{fmtPct(ensemble.final)}</td>
                      <td className="small muted">{ensemble.market != null ? `mezcla con mercado ${fmtPct(ensemble.market)}` : 'sin mercado'}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </Card>
          )}
        </div>
        <div className="col">
          {q.status === 'open' && (
            <Card title={userHas ? 'Actualizar mi pronóstico' : 'Mi pronóstico'}>
              <div className="col">
                <label className="field">
                  Probabilidad: <span className="num" style={{ fontSize: 18, color: 'var(--c-heading)' }}>{p} %</span>
                  <input type="range" min={1} max={99} value={p} onChange={(e) => setP(Number(e.target.value))} aria-label="Probabilidad" />
                </label>
                <label className="field">
                  Razonamiento (opcional)
                  <textarea rows={3} value={rationale} onChange={(e) => setRationale(e.target.value)} />
                </label>
                <button type="button" className="btn btn-primary" onClick={submitForecast} disabled={busy === 'forecast'}>
                  Registrar {p} %
                </button>
                {!userHas && <p className="muted small">La probabilidad del sistema se revela al registrar la tuya.</p>}
              </div>
            </Card>
          )}
          <Card title="Mercado enlazado">
            {q.market ? (
              <div className="small">
                {q.market.venue}: <strong className="num">{fmtPct(q.market.probability)}</strong> · dato {fmtDateTime(q.market.fetched_at)} · <ExtLink href={q.market.url}>ver ↗</ExtLink>
              </div>
            ) : (
              <p className="muted small">Sin mercado enlazado.</p>
            )}
            {q.status === 'open' && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setLinkOpen(true)}>
                Enlazar mercado
              </button>
            )}
          </Card>
          <Card title="Ensemble ATLAS">
            <p className="muted small">Cinco pronosticadores con enfoques distintos (outside view, inside view, abogado del diablo, mercado, historiador) y un agregador. Registra cada pieza como pronóstico.</p>
            <button type="button" className="btn" onClick={runEnsemble} disabled={!agentsEnabled || busy === 'ensemble' || q.status !== 'open'} title={agentsEnabled ? undefined : (agents?.message ?? undefined)}>
              {busy === 'ensemble' ? 'Calculando…' : 'Ensemble ATLAS'}
            </button>
            {!agentsEnabled && <div className="notice warn" style={{ marginTop: 6 }}>{agents?.message ?? 'Requiere ANTHROPIC_API_KEY.'}</div>}
          </Card>
          {q.status === 'open' && (
            <Card title="Resolver">
              <div className="row">
                <button type="button" className="btn btn-ghost" onClick={() => resolve(1)}>
                  Resolver SÍ
                </button>
                <button type="button" className="btn btn-ghost" onClick={() => resolve(0)}>
                  Resolver NO
                </button>
              </div>
            </Card>
          )}
        </div>
      </div>
      <Modal open={linkOpen} title="Enlazar un mercado de predicción" onClose={() => setLinkOpen(false)} wide>
        <input type="search" value={mq} onChange={(e) => setMq(e.target.value)} placeholder="Filtrar por texto…" style={{ width: '100%', marginBottom: 8 }} aria-label="Filtrar mercados" />
        <table className="table">
          <tbody>
            {filteredMarkets.map((m) => (
              <tr key={m.id}>
                <td>{m.question}</td>
                <td>{m.venue}</td>
                <td className="num">{fmtPct(m.probability)}</td>
                <td>
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={async () => {
                      await api.linkMarket(id, m.id)
                      setLinkOpen(false)
                      toast('Mercado enlazado y seguido')
                      reload()
                    }}
                  >
                    Enlazar
                  </button>
                </td>
              </tr>
            ))}
            {filteredMarkets.length === 0 && (
              <tr>
                <td className="muted">Sin mercados cargados. Actualiza mercados en la Sala de máquinas.</td>
              </tr>
            )}
          </tbody>
        </table>
      </Modal>
    </div>
  )
}

export default function Forecasts() {
  const { id } = useParams()
  const nav = useNavigate()
  const [params, setParams] = useSearchParams()
  const [tab, setTab] = useState<'open' | 'resolved' | 'calibration'>('open')
  const { data, error, loading, reload } = useAsync<{ questions: ForecastQuestion[] }>(() => api.forecasts(), [id])
  const newOpen = params.get('nuevo') === '1'
  const list = useMemo(() => (data?.questions ?? []).filter((q) => (tab === 'open' ? q.status === 'open' : q.status !== 'open')), [data, tab])

  if (id) return <QuestionDetail id={id} />

  return (
    <div>
      <div className="screen-head">
        <div>
          <h1>Pronósticos</h1>
          <div className="sub">Preguntas puntuables. Tu probabilidad antes que la del sistema; Brier y calibración al resolver.</div>
        </div>
        <div className="tools">
          <button type="button" className="btn btn-primary" onClick={() => setParams({ nuevo: '1' })}>
            Nueva pregunta
          </button>
        </div>
      </div>
      <Tabs
        tabs={[
          { id: 'open', label: 'Abiertas', count: data?.questions.filter((q) => q.status === 'open').length },
          { id: 'resolved', label: 'Resueltas', count: data?.questions.filter((q) => q.status !== 'open').length },
          { id: 'calibration', label: 'Calibración' },
        ]}
        value={tab}
        onChange={setTab}
      />
      <div style={{ paddingTop: 'var(--sp-3)' }}>
        {loading && !data && <Loading />}
        <ErrorBox error={error} retry={reload} />
        {tab === 'calibration' && <CalibrationPanel />}
        {tab !== 'calibration' && data && list.length === 0 && <EmptyState title={tab === 'open' ? 'Sin preguntas abiertas' : 'Sin preguntas resueltas'}>Crea una pregunta cerrada con criterio de resolución verificable. El filtro de calidad exige «?», ≥ 30 caracteres de criterio y tasa base entre 3 y 97 %.</EmptyState>}
        {tab !== 'calibration' && (
          <div className="biz-cards">
            {list.map((q) => (
              <Card key={q.id} title={<Link to={`/pronosticos/${q.id}`}>{q.title}</Link>} extra={<span className="muted small mono">cierra {fmtDateTime(q.close_at)}</span>}>
                <ProbBars q={q} revealSystem={false} />
                <div className="row wrap small muted" style={{ marginTop: 6 }}>
                  {q.domain && <span className="chip">{q.domain}</span>}
                  <CountryChips countries={q.countries} />
                  {q.market && <span>mercado {q.market.venue}</span>}
                  {q.origin_event_id && <Link to={`/eventos/${q.origin_event_id}`}>evento origen</Link>}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
      <Modal open={newOpen} title="Nueva pregunta de pronóstico" onClose={() => setParams({})} wide>
        <NewQuestionForm
          eventId={params.get('evento')}
          country={params.get('pais')}
          onCancel={() => setParams({})}
          onCreated={(qid) => {
            setParams({})
            nav(`/pronosticos/${qid}`)
          }}
        />
      </Modal>
    </div>
  )
}
