import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import type { DocumentDetail, NormativeTranslation, RedTeamReport } from '../../api/types'
import { fmtDateTime, fmtPct } from '../../lib/format'
import { blocLabel, ideologyLabel, sourceTypeLabel } from '../../lib/labels'
import { useAsync, useDietLog } from '../../lib/hooks'
import { useStore } from '../../state/store'
import { AgentStream } from '../ui/AgentStream'
import { CountryChips, DomainChip, ErrorBox, ExtLink, Level, Loading, ProvenanceChip, StatusIcon } from '../ui/basics'
import { MaterialityBar } from '../ui/MaterialityBar'

/** Documento abierto desde una afirmación o una cronología, con el fragmento citado resaltado. */
function DocumentView({ id, highlight }: { id: string; highlight?: string | null }) {
  const { data, error, loading } = useAsync<DocumentDetail>(() => api.document(id), [id])
  useDietLog({ document_id: id })
  const marked = useMemo(() => {
    const text = data?.text || data?.lede || ''
    if (!text) return null
    if (!highlight) return <>{text}</>
    const norm = (s: string) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
    const idx = norm(text).indexOf(norm(highlight).slice(0, 60))
    if (idx < 0) return <>{text}</>
    const end = idx + highlight.length
    return (
      <>
        {text.slice(0, idx)}
        <mark>{text.slice(idx, end)}</mark>
        {text.slice(end)}
      </>
    )
  }, [data, highlight])
  if (loading) return <Loading />
  if (error) return <ErrorBox error={error} />
  if (!data) return null
  return (
    <div className="doc-view col">
      <div className="row wrap small muted">
        <strong style={{ color: 'var(--c-text)' }}>{data.source_name}</strong>
        <span>tier {data.tier}</span>
        <span>{sourceTypeLabel(data.source_type)}</span>
        {data.ideology_label && <span>{ideologyLabel(data.ideology_label)}</span>}
        {data.region_bloc && <span>{blocLabel(data.region_bloc)}</span>}
        <span className="mono">{data.lang}</span>
        <span className="mono">{fmtDateTime(data.published_at)}</span>
      </div>
      <h3>{data.title}</h3>
      <div className="row wrap">
        <ExtLink href={data.url}>Abrir original ↗</ExtLink>
        {data.event_id && <Link to={`/eventos/${data.event_id}`}>Ver evento</Link>}
        {data.countries.length > 0 && <CountryChips countries={data.countries} />}
      </div>
      {data.lede && !data.text && <p className="lede">{highlight ? marked : data.lede}</p>}
      {data.text && <div className="fulltext">{marked}</div>}
      {data.claims.length > 0 && (
        <div>
          <div className="label" style={{ marginBottom: 4 }}>
            Afirmaciones extraídas de este documento
          </div>
          {data.claims.map((c) => (
            <div key={c.id} style={{ borderTop: '1px solid var(--c-line)', padding: '4px 0', fontSize: 'var(--fs-data)' }}>
              <div className="row wrap" style={{ marginBottom: 2 }}>
                <StatusIcon status={c.status} />
                <Level level={c.level} />
                <ProvenanceChip extractedBy={c.extracted_by} />
              </div>
              {c.text_canonical}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function RedTeamView({ r }: { r: RedTeamReport }) {
  return (
    <div className="col" style={{ fontSize: 'var(--fs-data)' }}>
      <div>
        <div className="label">Alternativa más fuerte</div>
        {r.strongest_alternative}
      </div>
      <div>
        <div className="label">Evidencia discriminante</div>
        <ul style={{ margin: '2px 0 0 16px', padding: 0 }}>
          {r.discriminating_evidence.map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      </div>
      <div>
        <div className="label">Sesgos probables</div>
        <ul style={{ margin: '2px 0 0 16px', padding: 0 }}>
          {r.likely_biases.map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      </div>
      <div>
        <div className="label">Riesgos de cola</div>
        {r.tail_risks.map((t, i) => (
          <div key={i} className="row" style={{ justifyContent: 'space-between' }}>
            <span>{t.description}</span>
            <span className="num">{fmtPct(t.rough_probability)}</span>
          </div>
        ))}
      </div>
      <div>
        <div className="label">La pregunta que nadie hace</div>
        <em>{r.question_nobody_asks}</em>
      </div>
      {r.model && (
        <div className="muted small">
          modelo {r.model} · {r.cost_usd?.toFixed(4)} USD
        </div>
      )}
    </div>
  )
}

function NormativeView({ r }: { r: NormativeTranslation }) {
  return (
    <div className="col" style={{ fontSize: 'var(--fs-data)' }}>
      {r.questions.map((q, i) => (
        <div key={i}>
          <strong>{q.question}</strong>
          {q.traditions.map((t, j) => (
            <div key={j} style={{ borderLeft: '3px solid var(--c-accent)', paddingLeft: 8, margin: '4px 0' }}>
              <div>
                <b>{t.name}</b>
                {t.key_works.length > 0 && <span className="muted"> · {t.key_works.join('; ')}</span>}
              </div>
              <div>{t.position_sketch}</div>
            </div>
          ))}
        </div>
      ))}
      {r.uncertainties.length > 0 && (
        <div>
          <div className="label">Incertidumbres</div>
          <ul style={{ margin: '2px 0 0 16px', padding: 0 }}>
            {r.uncertainties.map((u, i) => (
              <li key={i}>{u}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="muted small">Reconstrucción generada por un modelo{r.model ? ` (${r.model})` : ''}; no es la posición literal de ningún autor.</div>
    </div>
  )
}

function QuickNote({ inert = false }: { inert?: boolean }) {
  const { currentEvent, toast } = useStore()
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)
  const save = async () => {
    if (!text.trim()) return
    setSaving(true)
    const link = currentEvent ? `\n\nSobre: [[${currentEvent.title_neutral}]]` : ''
    try {
      await api.createNote({ body_text: `${text.trim()}${link}`, title: text.trim().slice(0, 60) })
      setText('')
      toast('Nota añadida al TALLER')
    } catch (e) {
      toast(e instanceof Error ? e.message : 'No se pudo guardar', 'warn')
    } finally {
      setSaving(false)
    }
  }
  return (
    <div className="quick-note" inert={inert}>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <span className="label">Nota rápida</span>
        {currentEvent && (
          <span className="small muted truncate" title={currentEvent.title_neutral} style={{ maxWidth: 180 }}>
            enlaza a [[{currentEvent.title_neutral}]]
          </span>
        )}
      </div>
      <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Apunta una idea, una objeción, una pregunta…" aria-label="Nota rápida" />
      <div className="row" style={{ justifyContent: 'flex-end' }}>
        <button type="button" className="btn btn-sm" onClick={save} disabled={saving || !text.trim()}>
          Añadir a TALLER
        </button>
      </div>
    </div>
  )
}

export function ContextPanel() {
  const { panel, setPanel, panelOpen, setPanelOpen, currentEvent } = useStore()
  const [title, setTitle] = useState('Panel contextual')
  useEffect(() => {
    if (!panel) setTitle(currentEvent ? 'Selección' : 'Panel contextual')
    else if (panel.kind === 'document') setTitle('Documento')
    else if (panel.kind === 'agent-stream' || panel.kind === 'agent-result') setTitle('Agente')
    else setTitle('Selección')
  }, [panel, currentEvent])

  let body: ReactNode = null
  if (panel?.kind === 'document') body = <DocumentView id={panel.id} highlight={panel.highlight} />
  else if (panel?.kind === 'agent-stream') body = <AgentStream title={panel.title} url={panel.url} method={panel.method} body={panel.body} runKey={panel.key} />
  else if (panel?.kind === 'agent-result') {
    body = (
      <div className="agent-stream">
        <div className="head">
          <strong>{panel.title}</strong>
        </div>
        {panel.resultKind === 'red_team' && <RedTeamView r={panel.result as RedTeamReport} />}
        {panel.resultKind === 'normative' && <NormativeView r={panel.result as NormativeTranslation} />}
        {panel.resultKind === 'generic' && <pre style={{ fontSize: 11, whiteSpace: 'pre-wrap' }}>{JSON.stringify(panel.result, null, 2)}</pre>}
      </div>
    )
  } else if (currentEvent) {
    body = (
      <div className="col" style={{ fontSize: 'var(--fs-data)' }}>
        <div className="label">Evento seleccionado</div>
        <Link to={`/eventos/${currentEvent.id}`} style={{ fontSize: 'var(--fs-ui)', color: 'var(--c-heading)' }}>
          {currentEvent.title_neutral}
        </Link>
        <div className="row wrap">
          <MaterialityBar value={currentEvent.materiality} breakdown={currentEvent.materiality_breakdown} />
          <DomainChip domain={currentEvent.domain} />
          <CountryChips countries={currentEvent.countries} />
        </div>
        <div className="muted">
          {currentEvent.n_sources} fuentes · {currentEvent.n_primary} primarias · {currentEvent.langs.join(', ')}
        </div>
        <div className="row wrap">
          <Link to={`/prisma/${currentEvent.id}`}>Prisma</Link>
          <Link to={`/pronosticos?evento=${currentEvent.id}`}>Pronósticos</Link>
        </div>
      </div>
    )
  } else {
    body = <div className="muted small">Aquí aparecen el detalle de la selección, la salida de los agentes en streaming y los documentos citados. Selecciona un evento o una afirmación.</div>
  }

  /* Un único <aside> en ambos estados, con los mismos hijos en las mismas posiciones: al plegar, el cuerpo
     y la nota se ocultan por CSS (.panel.closed) y quedan inertes, pero no se desmontan. Así AgentStream no
     cierra el stream ni relanza (y cobra) el agente al volver a abrir, y DocumentView no recarga. */
  return (
    <aside className={panelOpen ? 'panel' : 'panel closed'} aria-label={panelOpen ? 'Panel contextual' : 'Panel contextual plegado'}>
      <div className="panel-head">
        {panelOpen ? (
          <>
            <span className="label">{title}</span>
            <span className="row" style={{ gap: 2 }}>
              {panel && (
                <button type="button" className="btn-icon" onClick={() => setPanel(null)} aria-label="Limpiar el panel" title="Limpiar">
                  ✕
                </button>
              )}
              <button type="button" className="btn-icon" onClick={() => setPanelOpen(false)} aria-label="Plegar el panel contextual" title="Plegar">
                ▸
              </button>
            </span>
          </>
        ) : (
          <button type="button" className="btn-icon" onClick={() => setPanelOpen(true)} aria-label="Abrir el panel contextual" title="Abrir panel">
            ◂
          </button>
        )}
      </div>
      <div className="panel-body" inert={!panelOpen} aria-hidden={!panelOpen}>
        {body}
      </div>
      <QuickNote inert={!panelOpen} />
      {!panelOpen && <div className="vertical-label">Panel</div>}
    </aside>
  )
}
