import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Decision, MandoResponse } from '../api/types'
import { Card, EmptyState, ErrorBox, ExtLink, Loading } from '../components/ui/basics'
import { Modal } from '../components/ui/Modal'
import { fmtDate, fmtDateTime, fmtPct } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { channelLabel } from '../lib/labels'
import { useStore } from '../state/store'
import './screens.css'

function DecisionForm({ businesses, onDone }: { businesses: MandoResponse['businesses']; onDone: () => void }) {
  const [f, setF] = useState({ business_id: '', title: '', context: '', premises: '', alternatives: '', success_probability: 60, premortem: '', review_at: '' })
  const [busy, setBusy] = useState(false)
  const submit = async () => {
    setBusy(true)
    try {
      await api.createDecision({
        business_id: f.business_id || null,
        title: f.title,
        context: f.context || null,
        premises: f.premises.split('\n').map((s) => s.trim()).filter(Boolean),
        alternatives: f.alternatives.split('\n').map((s) => s.trim()).filter(Boolean),
        success_probability: f.success_probability / 100,
        premortem: f.premortem || null,
        review_at: f.review_at ? new Date(f.review_at).toISOString() : null,
      })
      onDone()
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="col">
      <label className="field">
        Negocio
        <select value={f.business_id} onChange={(e) => setF({ ...f, business_id: e.target.value })}>
          <option value="">— general —</option>
          {businesses.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        Decisión
        <input type="text" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} />
      </label>
      <label className="field">
        Contexto
        <textarea rows={2} value={f.context} onChange={(e) => setF({ ...f, context: e.target.value })} />
      </label>
      <div className="two-col">
        <label className="field">
          Premisas explícitas (una por línea)
          <textarea rows={4} value={f.premises} onChange={(e) => setF({ ...f, premises: e.target.value })} />
        </label>
        <label className="field">
          Alternativas descartadas (una por línea)
          <textarea rows={4} value={f.alternatives} onChange={(e) => setF({ ...f, alternatives: e.target.value })} />
        </label>
      </div>
      <label className="field">
        Probabilidad de éxito: <span className="num">{f.success_probability} %</span>
        <input type="range" min={1} max={99} value={f.success_probability} onChange={(e) => setF({ ...f, success_probability: Number(e.target.value) })} />
      </label>
      <label className="field">
        Pre-mortem («es dentro de 18 meses y fracasó: ¿por qué?»)
        <textarea rows={3} value={f.premortem} onChange={(e) => setF({ ...f, premortem: e.target.value })} />
      </label>
      <label className="field">
        Fecha de revisión
        <input type="date" value={f.review_at} onChange={(e) => setF({ ...f, review_at: e.target.value })} />
      </label>
      <div className="row" style={{ justifyContent: 'flex-end' }}>
        <button type="button" className="btn btn-primary" onClick={submit} disabled={busy || !f.title.trim()}>
          Registrar decisión
        </button>
      </div>
    </div>
  )
}

function DecisionRow({ d, onOutcome }: { d: Decision; onOutcome: (d: Decision) => void }) {
  return (
    <Card title={d.title} extra={<span className="muted small mono">{fmtDate(d.decided_at)}</span>}>
      <div className="row wrap small muted" style={{ marginBottom: 4 }}>
        {d.business_name && <span className="chip">{d.business_name}</span>}
        {d.success_probability != null && <span>éxito estimado {fmtPct(d.success_probability)}</span>}
        {d.review_at && <span>revisar {fmtDate(d.review_at)}</span>}
      </div>
      {d.context && <p className="small">{d.context}</p>}
      <div className="two-col small">
        <div>
          <div className="label">Premisas</div>
          <ul style={{ margin: '2px 0 0 16px', padding: 0 }}>
            {d.premises.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </div>
        <div>
          <div className="label">Alternativas descartadas</div>
          <ul style={{ margin: '2px 0 0 16px', padding: 0 }}>
            {d.alternatives.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </div>
      </div>
      {d.premortem && (
        <div className="small" style={{ marginTop: 6 }}>
          <span className="label">Pre-mortem</span> {d.premortem}
        </div>
      )}
      <div style={{ marginTop: 8 }}>
        {d.outcome ? (
          <div className="notice">
            <strong>Desenlace:</strong> {d.outcome}
            {d.lessons && <div>Lecciones: {d.lessons}</div>}
          </div>
        ) : (
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => onOutcome(d)}>
            Registrar desenlace
          </button>
        )}
      </div>
    </Card>
  )
}

export default function Mando() {
  const { data, error, loading, reload } = useAsync<MandoResponse>(() => api.mando(), [])
  const { toast, setPanel } = useStore()
  const [newOpen, setNewOpen] = useState(false)
  const [outcomeFor, setOutcomeFor] = useState<Decision | null>(null)
  const [outcome, setOutcome] = useState({ outcome: '', lessons: '' })

  const dismiss = async (id: string) => {
    await api.dismissAlert(id)
    toast('Alerta descartada')
    reload()
  }

  return (
    <div>
      <div className="screen-head">
        <div>
          <h1>Mando</h1>
          <div className="sub">El mundo traducido a decisiones para tus negocios: exposición por canal, radar regulatorio y diario de decisiones.</div>
        </div>
        <div className="tools">
          <button type="button" className="btn btn-primary" onClick={() => setNewOpen(true)}>
            Nueva decisión
          </button>
        </div>
      </div>
      {loading && !data && <Loading />}
      <ErrorBox error={error} retry={reload} />
      {data && (
        <>
          <div className="notice" style={{ marginBottom: 12 }}>
            {data.profile_note}
          </div>
          <section>
            <div className="biz-cards">
              {data.businesses.map((b) => (
                <Card key={b.id} title={b.name} extra={<span className={`chip ${b.alerts_7d ? 'accent' : ''}`}>{b.alerts_7d} alertas 7 d</span>}>
                  <dl className="kv">
                    <dt>Sectores</dt>
                    <dd>{b.sectors.join(', ') || '—'}</dd>
                    <dt>Jurisdicciones</dt>
                    <dd className="mono">{b.jurisdictions.join(' ') || '—'}</dd>
                    <dt>Regulación</dt>
                    <dd>{b.regulations.join('; ') || '—'}</dd>
                    <dt>Divisas</dt>
                    <dd className="mono">{b.currencies.join(' ') || '—'}</dd>
                    {b.keywords.length > 0 && (
                      <>
                        <dt>Palabras clave</dt>
                        <dd>{b.keywords.join(', ')}</dd>
                      </>
                    )}
                  </dl>
                </Card>
              ))}
              {data.businesses.length === 0 && <EmptyState title="Sin negocios en el perfil">Añade tus empresas en config/perfil.yaml y ejecuta `atlas seed`.</EmptyState>}
            </div>
          </section>

          <div className="two-col">
            <section className="section">
              <div className="section-head">
                <h2>Alertas de exposición</h2>
                <span className="muted small">{data.alerts.length} activas</span>
              </div>
              {data.alerts.length === 0 && <p className="muted small">Sin alertas. Se generan por reglas de jurisdicción, sector y palabra clave sobre cada evento nuevo.</p>}
              {data.alerts.map((a) => (
                <div key={a.id} className="alert-row">
                  <div>
                    <div className="row wrap">
                      <span className="chip dark">{channelLabel(a.channel)}</span>
                      <span className="num">confianza {fmtPct(a.confidence)}</span>
                      <span className="chip">{a.business_name}</span>
                      <span className="muted small mono">{fmtDateTime(a.created_at)}</span>
                    </div>
                    <div style={{ margin: '2px 0' }}>{a.explanation}</div>
                    <Link to={`/eventos/${a.event_id}`}>{a.title_neutral ?? 'evento'}</Link>
                    {a.materiality != null && <span className="muted small"> · materialidad {a.materiality.toFixed(0)}</span>}
                  </div>
                  <div>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => dismiss(a.id)}>
                      Descartar
                    </button>
                  </div>
                </div>
              ))}
            </section>
            <section className="section">
              <div className="section-head">
                <h2>Radar regulatorio</h2>
                <span className="muted small">documentos primarios (14 d) que tocan tu regulación</span>
              </div>
              {data.regulatory.length === 0 && <p className="muted small">Ningún documento oficial coincide con los términos regulatorios del perfil en 14 días.</p>}
              {data.regulatory.map((d) => (
                <div key={d.id} style={{ padding: '6px 0', borderBottom: '1px solid var(--c-line)', fontSize: 'var(--fs-data)' }}>
                  <div className="row wrap small muted">
                    <strong style={{ color: 'var(--c-text)' }}>{d.source_name}</strong>
                    <span className="mono">{d.source_country}</span>
                    <span className="mono">{fmtDateTime(d.published_at)}</span>
                    {d.hits?.map((h) => (
                      <span key={h} className="chip accent">
                        {h}
                      </span>
                    ))}
                  </div>
                  <button type="button" className="btn-link" style={{ textAlign: 'left' }} onClick={() => setPanel({ kind: 'document', id: d.id })}>
                    {d.title}
                  </button>{' '}
                  <ExtLink href={d.url}>↗</ExtLink>
                </div>
              ))}
            </section>
          </div>

          <section className="section">
            <div className="section-head">
              <h2>Diario de decisiones</h2>
              <span className="muted small">{data.decisions.length} registradas · se puntúan como un pronóstico</span>
            </div>
            {data.decisions.length === 0 && <EmptyState title="Sin decisiones">Registra la primera con premisas explícitas, alternativas descartadas, probabilidad de éxito y pre-mortem.</EmptyState>}
            <div className="biz-cards">
              {data.decisions.map((d) => (
                <DecisionRow key={d.id} d={d} onOutcome={setOutcomeFor} />
              ))}
            </div>
          </section>
        </>
      )}
      <Modal open={newOpen} title="Nueva decisión" onClose={() => setNewOpen(false)} wide>
        <DecisionForm
          businesses={data?.businesses ?? []}
          onDone={() => {
            setNewOpen(false)
            toast('Decisión registrada')
            reload()
          }}
        />
      </Modal>
      <Modal open={!!outcomeFor} title={`Desenlace · ${outcomeFor?.title ?? ''}`} onClose={() => setOutcomeFor(null)}>
        <div className="col">
          <label className="field">
            Qué pasó
            <textarea rows={3} value={outcome.outcome} onChange={(e) => setOutcome({ ...outcome, outcome: e.target.value })} />
          </label>
          <label className="field">
            Lecciones
            <textarea rows={3} value={outcome.lessons} onChange={(e) => setOutcome({ ...outcome, lessons: e.target.value })} />
          </label>
          <div className="row" style={{ justifyContent: 'flex-end' }}>
            <button
              type="button"
              className="btn btn-primary"
              disabled={!outcome.outcome.trim()}
              onClick={async () => {
                if (!outcomeFor) return
                await api.decisionOutcome(outcomeFor.id, { outcome: outcome.outcome, lessons: outcome.lessons || undefined })
                setOutcomeFor(null)
                setOutcome({ outcome: '', lessons: '' })
                reload()
              }}
            >
              Guardar
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
