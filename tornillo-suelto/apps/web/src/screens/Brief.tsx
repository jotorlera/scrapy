import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Brief as BriefT, BriefLatest } from '../api/types'
import { CountryChips, DomainChip, EmptyState, ErrorBox, ExtLink, Loading, ProvenanceChip, StatusIcon } from '../components/ui/basics'
import { Markdown } from '../components/ui/Markdown'
import { QuoteHover } from '../components/ui/QuoteHover'
import { fmtDateTime, fmtLongDate } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { composedByLabel, levelLabel } from '../lib/labels'
import { useStore } from '../state/store'
import './screens.css'

export default function Brief() {
  const [params, setParams] = useSearchParams()
  const kind = params.get('tipo') === 'executive' ? 'executive' : 'study'
  const briefId = params.get('id')
  const { agentsEnabled, agents, toast, setPanel } = useStore()
  const [busy, setBusy] = useState<string | null>(null)
  const latest = useAsync<BriefLatest>(() => api.briefLatest(kind), [kind, briefId])
  const specific = useAsync<{ brief: BriefT } | null>(() => (briefId ? api.brief(briefId) : Promise.resolve(null)), [briefId])
  const brief = briefId ? specific.data?.brief ?? null : latest.data?.brief ?? null
  const loading = latest.loading || specific.loading

  const generate = async () => {
    setBusy('gen')
    try {
      await api.briefGenerate(kind, kind === 'executive' ? 168 : 24)
      toast('Brief generado con las reglas de composición')
      setParams(kind === 'executive' ? { tipo: 'executive' } : {})
      latest.reload()
    } catch (e) {
      toast(e instanceof ApiError ? e.userMessage : String(e), 'warn')
    } finally {
      setBusy(null)
    }
  }
  const redact = async () => {
    if (!brief) return
    setBusy('redact')
    try {
      await api.briefRedact(brief.id)
      toast('Brief redactado por el editor')
      latest.reload()
      specific.reload()
    } catch (e) {
      toast(e instanceof ApiError ? e.userMessage : String(e), 'warn')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div>
      <div className="screen-head no-print">
        <div>
          <h1>Brief</h1>
          <div className="sub">Diez minutos de lectura: hechos con cita, divergencia narrativa, primaria, por qué importa y concepto del grado.</div>
        </div>
        <div className="tools">
          <div className="seg">
            <button type="button" aria-pressed={kind === 'study'} onClick={() => setParams({})}>
              Estudio
            </button>
            <button type="button" aria-pressed={kind === 'executive'} onClick={() => setParams({ tipo: 'executive' })}>
              Ejecutivo
            </button>
          </div>
          <button type="button" className="btn" onClick={generate} disabled={busy !== null}>
            {busy === 'gen' ? 'Componiendo…' : 'Generar ahora'}
          </button>
          <button type="button" className="btn btn-ghost" onClick={redact} disabled={!brief || !agentsEnabled || busy !== null} title={agentsEnabled ? undefined : (agents?.message ?? undefined)}>
            {busy === 'redact' ? 'Redactando…' : 'Redactar con el editor'}
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => window.print()} disabled={!brief}>
            Imprimir / PDF
          </button>
        </div>
      </div>
      {loading && !brief && <Loading />}
      <ErrorBox error={latest.error ?? specific.error} />
      {!loading && !brief && (
        <EmptyState
          title={`Todavía no hay brief ${kind === 'executive' ? 'ejecutivo' : 'de estudio'}`}
          actions={
            <button type="button" className="btn btn-primary" onClick={generate}>
              Generar ahora
            </button>
          }
        >
          El planificador lo compone a las {agents ? '07:00' : '07:00'} (ajuste `hora_brief`). También puedes generarlo ahora con las reglas deterministas; con clave, el editor lo redacta.
        </EmptyState>
      )}
      {brief && (
        <article className="brief-doc">
          <div className="kicker">
            <span>{brief.kind === 'executive' ? 'Brief ejecutivo' : 'Brief de estudio'}</span>
            <span>{fmtLongDate(brief.date)}</span>
            <span>ventana {brief.window_hours} h</span>
            <span>~{Math.round(brief.reading_time_min)} min</span>
            <ProvenanceChip composedBy={composedByLabel(brief.composed_by)} />
          </div>
          <h1>TORNILLO SUELTO · {brief.kind === 'executive' ? 'lo que decidir esta semana' : 'lo que ha cambiado'}</h1>
          <p className="muted" style={{ fontSize: 14 }}>
            {brief.n_events_considered} eventos considerados · compuesto {fmtDateTime(brief.created_at)} · Dr. José Francisco Tornero-Aguilera
          </p>

          {brief.redaction_md && (
            <section>
              <h2>Redacción del editor</h2>
              <Markdown text={brief.redaction_md} />
              <p className="muted small">Texto generado por el modelo a partir del contenido compuesto por reglas; los hechos se citan por claim_id.</p>
            </section>
          )}

          {brief.sections.map((s) => (
            <section key={s.name}>
              <h2>{s.name}</h2>
              {s.items.map((it) => (
                <div key={it.event_id} className="brief-item">
                  <h3>
                    <Link to={`/eventos/${it.event_id}`} style={{ color: 'var(--c-heading)' }}>
                      {it.title}
                    </Link>
                  </h3>
                  <div className="row wrap small muted" style={{ marginBottom: 6 }}>
                    <DomainChip domain={it.domain} />
                    <CountryChips countries={it.countries} />
                    <span className="num">materialidad {it.materiality?.toFixed(0)}</span>
                  </div>
                  {it.facts.length > 0 && (
                    <ul className="facts">
                      {it.facts.map((f) => (
                        <li key={f.claim_id}>
                          <StatusIcon status={f.status} withLabel={false} />
                          <span className="level" data-level={f.level}>
                            {levelLabel(f.level)}
                          </span>
                          <QuoteHover quote={f.text} source={f.source}>
                            <button type="button" className="btn-link" style={{ textAlign: 'left', color: 'inherit', font: 'inherit' }} onClick={() => setPanel({ kind: 'document', id: f.document_id, highlight: f.text })}>
                              {f.text.length > 260 ? `${f.text.slice(0, 259)}…` : f.text}
                            </button>
                          </QuoteHover>
                        </li>
                      ))}
                    </ul>
                  )}
                  <div className="line">
                    <span className="k">Divergencia</span> {it.narrative_divergence}
                  </div>
                  <div className="line">
                    <span className="k">Primaria</span> {it.primary_source ? <ExtLink href={it.primary_source.url}>{it.primary_source.name}: {it.primary_source.title}</ExtLink> : <span className="muted">sin documento primario</span>}
                  </div>
                  <div className="line">
                    <span className="k">Por qué importa</span> {it.why_it_matters}
                  </div>
                  <div className="line">
                    <span className="k">Concepto del grado</span> {it.course_concept ? <Link to={`/agora?tab=tutor&tema=${encodeURIComponent(it.course_concept)}`}>{it.course_concept}</Link> : <span className="muted">—</span>}
                  </div>
                  {it.exposures.length > 0 && (
                    <div className="line">
                      <span className="k">Tus negocios</span> {it.exposures.map((x) => `${x.name} (${x.channel})`).join(' · ')}
                    </div>
                  )}
                </div>
              ))}
            </section>
          ))}

          <div className="brief-close">
            <div className="label">Pregunta de pronóstico</div>
            {brief.forecast_prompt ? (
              <p>
                <Link to={`/pronosticos/${brief.forecast_prompt.id}`}>{brief.forecast_prompt.title}</Link> <span className="muted small">(cierra {fmtDateTime(brief.forecast_prompt.close_at)})</span>
              </p>
            ) : (
              <p className="muted">No hay preguntas abiertas: crea una en Pronósticos.</p>
            )}
            <div className="label">Cuestión socrática</div>
            <p>
              {brief.socratic_prompt}{' '}
              <Link to={`/agora?tab=tutor&tema=${encodeURIComponent(brief.socratic_prompt)}`} className="small no-print">
                Discutirla con el tutor →
              </Link>
            </p>
          </div>

          {latest.data?.history && latest.data.history.length > 0 && (
            <section className="no-print">
              <h2>Historial</h2>
              <table className="table">
                <tbody>
                  {latest.data.history.map((h) => (
                    <tr key={h.id} className={h.id === brief.id ? 'active' : undefined}>
                      <td className="mono">{h.date}</td>
                      <td>{h.kind === 'executive' ? 'ejecutivo' : 'estudio'}</td>
                      <td className="muted">{composedByLabel(h.composed_by)}</td>
                      <td className="mono muted">{fmtDateTime(h.created_at)}</td>
                      <td>
                        <button type="button" className="btn-link" onClick={() => setParams({ id: h.id, tipo: h.kind })}>
                          abrir
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </article>
      )}
    </div>
  )
}
