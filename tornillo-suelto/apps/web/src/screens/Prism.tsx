import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { EventSummary, PrismResponse } from '../api/types'
import { Card, EmptyState, ErrorBox, ExtLink, InfoIcon, Loading } from '../components/ui/basics'
import { MaterialityBar } from '../components/ui/MaterialityBar'
import { fmt1, fmt2, seqColor } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { axisLabel, axisValueLabel, blocLabel, ideologyLabel, stateRelationLabel } from '../lib/labels'
import { useStore } from '../state/store'
import './screens.css'

function exportCsv(p: PrismResponse) {
  const { rows, cols, cells } = p.matrix
  const lines = [['ideologia', ...cols.map(blocLabel)].join(';')]
  for (const r of rows) lines.push([ideologyLabel(r), ...cols.map((c) => String(cells[r]?.[c] ?? 0))].join(';'))
  lines.push('')
  lines.push('silencios;eje;ecosistema;esperado;observado;S')
  for (const s of p.silences) lines.push(`;${s.axis};${s.ecosystem};${s.expected};${s.observed};${s.s}`)
  lines.push('')
  lines.push(`metodo;${p.method.silence};${p.method.lexicon}`)
  lines.push(`evento;${p.event.title_neutral.replace(/;/g, ',')};${p.event.id}`)
  const blob = new Blob([`﻿${lines.join('\n')}`], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `prisma_${p.event.id.slice(0, 8)}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}

export default function Prism() {
  const { eventId } = useParams()
  const nav = useNavigate()
  const { setCurrentEvent } = useStore()
  const [candidates, setCandidates] = useState<EventSummary[]>([])
  useEffect(() => {
    api
      .events({ hours: 168, limit: 200 })
      .then((r) => setCandidates(r.events.slice().sort((a, b) => b.n_sources - a.n_sources).slice(0, 30)))
      .catch(() => undefined)
  }, [])
  useEffect(() => {
    if (!eventId && candidates.length) nav(`/prisma/${candidates[0].id}`, { replace: true })
  }, [eventId, candidates, nav])

  const { data, error, loading } = useAsync<PrismResponse | null>(() => (eventId ? api.prism(eventId) : Promise.resolve(null)), [eventId])
  useEffect(() => {
    if (data) setCurrentEvent(data.event)
  }, [data, setCurrentEvent])

  const max = useMemo(() => {
    if (!data) return 1
    return Math.max(1, ...data.matrix.rows.flatMap((r) => data.matrix.cols.map((c) => data.matrix.cells[r]?.[c] ?? 0)))
  }, [data])

  const silentBloc = (bloc: string) => data?.axes.bloc?.[bloc]?.silent
  const silentIdeo = (ideo: string) => data?.axes.ideology?.[ideo]?.silent
  const overBloc = (bloc: string) => data?.axes.bloc?.[bloc]?.over
  const overIdeo = (ideo: string) => data?.axes.ideology?.[ideo]?.over

  return (
    <div>
      <div className="screen-head">
        <div>
          <h1>Prisma</h1>
          <div className="sub">Quién cuenta cada historia, cómo y quién la calla: matriz de cobertura, índice de silencio y vocabulario diferencial.</div>
        </div>
        <div className="tools">
          <select value={eventId ?? ''} onChange={(e) => nav(`/prisma/${e.target.value}`)} aria-label="Evento" style={{ maxWidth: 460 }}>
            {!eventId && <option value="">Elige un evento…</option>}
            {eventId && !candidates.some((c) => c.id === eventId) && data && <option value={eventId}>{data.event.title_neutral}</option>}
            {candidates.map((c) => (
              <option key={c.id} value={c.id}>
                {c.n_sources} f. · {c.title_neutral.slice(0, 80)}
              </option>
            ))}
          </select>
          {data && (
            <button type="button" className="btn" onClick={() => exportCsv(data)}>
              Exportar matriz (CSV)
            </button>
          )}
        </div>
      </div>
      {loading && <Loading />}
      <ErrorBox error={error} />
      {!eventId && !candidates.length && !loading && <EmptyState title="Sin eventos recientes">Prisma necesita eventos con varias fuentes. Lanza la ingesta en la Sala de máquinas.</EmptyState>}
      {data && (
        <div className="col" style={{ gap: 'var(--sp-4)' }}>
          <div className="row wrap">
            <Link to={`/eventos/${data.event.id}`} style={{ fontSize: 16, color: 'var(--c-heading)' }}>
              {data.event.title_neutral}
            </Link>
            <MaterialityBar value={data.event.materiality} breakdown={data.event.materiality_breakdown} />
            <span className="muted small">{data.n_docs} documentos</span>
          </div>

          <section className="section" style={{ marginTop: 0 }}>
            <div className="section-head">
              <h2>Matriz de cobertura</h2>
              <span className="muted small">filas: ecosistema ideológico · columnas: bloque regional · celda: nº de documentos</span>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="prism-matrix">
                <thead>
                  <tr>
                    <th />
                    {data.matrix.cols.map((c) => (
                      <th key={c} style={{ color: silentBloc(c) ? 'var(--c-warn)' : undefined }}>
                        {blocLabel(c)}
                        {silentBloc(c) ? ' ⚠' : ''}
                      </th>
                    ))}
                    <th className="num">Σ</th>
                  </tr>
                </thead>
                <tbody>
                  {data.matrix.rows.map((r) => {
                    const sum = data.matrix.cols.reduce((s, c) => s + (data.matrix.cells[r]?.[c] ?? 0), 0)
                    return (
                      <tr key={r}>
                        <th className="row-h" style={{ color: silentIdeo(r) ? 'var(--c-warn)' : undefined }}>
                          {ideologyLabel(r)}
                          {silentIdeo(r) ? ' ⚠' : ''}
                        </th>
                        {data.matrix.cols.map((c) => {
                          const v = data.matrix.cells[r]?.[c] ?? 0
                          const silent = (silentBloc(c) || silentIdeo(r)) && v === 0
                          const over = (overBloc(c) || overIdeo(r)) && v > 0
                          return (
                            <td key={c}>
                              <div className={`cell ${silent ? 'silent' : ''} ${over ? 'over' : ''}`} style={{ background: v ? seqColor(0.15 + (0.85 * v) / max) : undefined, color: v ? (v / max > 0.5 ? 'var(--c-bg)' : '#000') : undefined }} title={`${ideologyLabel(r)} × ${blocLabel(c)}: ${v}`}>
                                {v || (silent ? '∅' : '·')}
                              </div>
                            </td>
                          )
                        })}
                        <td>
                          <div className="cell">{sum}</div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div className="prism-legend">
              <span>
                <i style={{ background: seqColor(0.2) }} /> pocos documentos
              </span>
              <span>
                <i style={{ background: seqColor(1) }} /> muchos
              </span>
              <span>
                <i style={{ outline: '2px solid var(--c-warn)', outlineOffset: -2 }} /> ∅ silencio (S &gt; 2, E ≥ 5)
              </span>
              <span>
                <i style={{ outline: '2px dashed var(--c-ink)', outlineOffset: -2 }} /> sobrecobertura
              </span>
            </div>
          </section>

          <div className="two-col">
            <section className="section">
              <div className="section-head">
                <h2>
                  Silencios{' '}
                  <InfoIcon label="Método del índice de silencio">
                    <h4>Índice de silencio</h4>
                    <p>{data.method.silence}</p>
                    <p className="muted">E: cobertura esperada según la cuota del ecosistema en los últimos 30 días; O: observada; S: desviación estandarizada de Poisson.</p>
                  </InfoIcon>
                </h2>
              </div>
              {data.silences.length === 0 && <p className="muted small">Ningún ecosistema calla este evento de forma estadísticamente significativa.</p>}
              {data.silences.length > 0 && (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Eje</th>
                      <th>Ecosistema</th>
                      <th className="num">Esperado</th>
                      <th className="num">Observado</th>
                      <th className="num">S</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.silences.map((s, i) => (
                      <tr key={i}>
                        <td>{axisLabel(s.axis)}</td>
                        <td>{axisValueLabel(s.axis, s.ecosystem)}</td>
                        <td className="num">{fmt2(s.expected)}</td>
                        <td className="num">{s.observed}</td>
                        <td className="num" style={{ color: 'var(--c-warn)' }}>
                          {fmt2(s.s)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <details style={{ marginTop: 8 }}>
                <summary className="small muted" style={{ cursor: 'pointer' }}>
                  Todos los ejes (esperado / observado / S)
                </summary>
                {Object.entries(data.axes).map(([axis, cells]) => (
                  <div key={axis} style={{ marginTop: 6 }}>
                    <div className="label">{axisLabel(axis)}</div>
                    <table className="table">
                      <tbody>
                        {Object.entries(cells)
                          .sort((a, b) => b[1].s - a[1].s)
                          .map(([k, c]) => (
                            <tr key={k}>
                              <td>{axisValueLabel(axis, k)}</td>
                              <td className="num">{fmt2(c.expected)}</td>
                              <td className="num">{c.observed}</td>
                              <td className="num" style={{ color: c.silent ? 'var(--c-warn)' : undefined }}>
                                {fmt2(c.s)}
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                ))}
              </details>
            </section>

            <section className="section">
              <div className="section-head">
                <h2>
                  Vocabulario diferencial{' '}
                  <InfoIcon label="Método del léxico diferencial">
                    <h4>Léxico diferencial</h4>
                    <p>{data.method.lexicon}</p>
                    <p className="muted">z: puntuación log-odds estandarizada del término frente al resto de ecosistemas; se muestran los términos con mayor z por grupo.</p>
                  </InfoIcon>
                </h2>
              </div>
              {(['ideology', 'bloc'] as const).map((axis) => {
                const groups = Object.entries(data.lexicon[axis]).filter(([, terms]) => terms.length)
                if (!groups.length) return <p key={axis} className="muted small">Sin léxico diferencial por {axisLabel(axis).toLowerCase()} (hace falta más de un grupo con texto).</p>
                return (
                  <div key={axis}>
                    <div className="label" style={{ margin: '6px 0 4px' }}>
                      por {axisLabel(axis).toLowerCase()}
                    </div>
                    {groups.map(([g, terms]) => (
                      <div key={g} className="lexicon-group">
                        <div className="small" style={{ marginBottom: 2 }}>
                          {axisValueLabel(axis, g)}
                        </div>
                        <div className="terms">
                          {terms.slice(0, 12).map((t) => (
                            <span key={t.term} className="chip mono" title={`z = ${t.z} · ${t.count} apariciones`} style={{ background: `color-mix(in oklab, var(--c-accent) ${Math.round(20 + Math.min(1, t.z / 3) * 80)}%, var(--c-bg))`, color: 'var(--c-text)' }}>
                              {t.term} <span style={{ opacity: 0.7 }}>z {fmt1(t.z)}</span>
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )
              })}
            </section>
          </div>

          <div className="two-col">
            <section className="section">
              <div className="section-head">
                <h2>Titulares representativos por ecosistema</h2>
              </div>
              {Object.entries(data.representative).map(([eco, items]) => (
                <Card key={eco} title={ideologyLabel(eco)} className="flat" style={{ marginBottom: 10 }}>
                  {items.map((it, i) => (
                    <div key={i} style={{ fontSize: 'var(--fs-data)', padding: '3px 0', borderBottom: '1px solid var(--c-line)' }}>
                      <ExtLink href={it.url}>{it.title}</ExtLink>
                      <div className="muted small">
                        {it.source} · {blocLabel(it.bloc)} · {it.lang}
                      </div>
                    </div>
                  ))}
                </Card>
              ))}
            </section>
            <section className="section">
              <div className="section-head">
                <h2>Medios estatales</h2>
                <span className="muted small">{data.state_media.length}</span>
              </div>
              {data.state_media.length === 0 && <p className="muted small">Ningún medio con control o alineamiento estatal cubre este evento.</p>}
              {data.state_media.map((d) => (
                <div key={d.id} style={{ fontSize: 'var(--fs-data)', padding: '4px 0', borderBottom: '1px solid var(--c-line)' }}>
                  <div className="row wrap">
                    <strong>{d.source_name}</strong>
                    <span className="chip dark">{stateRelationLabel(d.state_relation)}</span>
                    <span className="chip mono">{d.country}</span>
                    <span className="muted">{blocLabel(d.region_bloc)}</span>
                  </div>
                  <ExtLink href={d.url}>{d.title}</ExtLink>
                  {d.lede && <div className="muted">{d.lede.slice(0, 200)}</div>}
                </div>
              ))}
              {data.frames.length === 0 && (
                <p className="muted small" style={{ marginTop: 12 }}>
                  Marcos (familias de encuadre): pendiente de implementar; el clasificador aún no está cableado en el pipeline (con o sin clave).
                </p>
              )}
            </section>
          </div>
        </div>
      )}
    </div>
  )
}
