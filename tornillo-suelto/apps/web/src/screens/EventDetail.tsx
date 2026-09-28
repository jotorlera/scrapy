import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Claim, EventDetail as EventDetailT, EventSummary } from '../api/types'
import { Card, Chip, CountryChips, DomainChip, EmptyState, ErrorBox, ExtLink, Level, Loading, ProvenanceChip, StatusIcon, Tabs } from '../components/ui/basics'
import { EventCard } from '../components/ui/EventCard'
import { MaterialityBar } from '../components/ui/MaterialityBar'
import { QuoteHover } from '../components/ui/QuoteHover'
import { fmtAgo, fmtDateTime, fmtPct, fmtVolume, seqColor } from '../lib/format'
import { useAsync, useDietLog } from '../lib/hooks'
import { blocLabel, channelLabel, dimensionLabel, ideologyLabel, IDEOLOGY_ORDER, paywallLabel, sourceTypeLabel, stateRelationLabel, TRADITIONS } from '../lib/labels'
import { useStore } from '../state/store'
import './screens.css'

type Tab = 'what' | 'unknown' | 'disputed' | 'timeline' | 'sources' | 'context' | 'impact' | 'forecasts'

function MiniMatrix({ event }: { event: EventSummary }) {
  const m = event.coverage_stats?.matrix ?? {}
  const rows = IDEOLOGY_ORDER.filter((r) => m[r])
  const cols = Array.from(new Set(rows.flatMap((r) => Object.keys(m[r]))))
  if (!rows.length) return null
  const max = Math.max(1, ...rows.flatMap((r) => cols.map((c) => m[r][c] ?? 0)))
  return (
    <Link to={`/prisma/${event.id}`} className="mini-matrix" style={{ gridTemplateColumns: `repeat(${cols.length}, 9px)` }} title={`Matriz de cobertura ${rows.length}×${cols.length} · abrir Prisma`} aria-label="Abrir Prisma">
      {rows.map((r) => cols.map((c) => <i key={`${r}-${c}`} style={{ background: m[r][c] ? seqColor(0.25 + (0.75 * m[r][c]) / max) : undefined }} title={`${ideologyLabel(r)} × ${blocLabel(c)}: ${m[r][c] ?? 0}`} />))}
    </Link>
  )
}

function ClaimRow({ c, onOpenDoc }: { c: Claim; onOpenDoc: (id: string, quote: string) => void }) {
  const primaryQuote = c.evidence.find((e) => e.document_id === c.document_id)?.quote ?? c.text_original ?? c.text_canonical
  return (
    <div className="claim">
      <div className="side">
        <StatusIcon status={c.status} />
        <Level level={c.level} />
        <ProvenanceChip extractedBy={c.extracted_by} />
      </div>
      <div>
        <QuoteHover quote={primaryQuote} source={`${c.source_name} · ${fmtDateTime(c.first_seen_at)}`}>
          <span className="text">{c.text_canonical}</span>
        </QuoteHover>
        {c.attributed_to && <div className="small muted">Atribuida a: {c.attributed_to}</div>}
        <div className="foot">
          <button type="button" className="btn-link" onClick={() => onOpenDoc(c.document_id, primaryQuote)}>
            {c.source_name} (tier {c.source_tier})
          </button>
          <span>{fmtDateTime(c.first_seen_at)}</span>
          <span>{c.evidence.length} evidencia{c.evidence.length === 1 ? '' : 's'}</span>
          <span title="Probabilidad de merecer verificación">cw {c.check_worthy.toFixed(2)}</span>
          {c.revisions.length > 0 && <span>{c.revisions.length} revisión(es)</span>}
        </div>
      </div>
    </div>
  )
}

export default function EventDetail() {
  const { id = '' } = useParams()
  const nav = useNavigate()
  const { setCurrentEvent, setPanel, agentsEnabled, agents, toast } = useStore()
  const [tab, setTab] = useState<Tab>('what')
  const [tradition, setTradition] = useState(TRADITIONS[0])
  const [busy, setBusy] = useState<string | null>(null)
  const { data, error, loading, reload } = useAsync<EventDetailT>(() => api.event(id), [id])
  useDietLog({ event_id: id })

  useEffect(() => {
    if (data) setCurrentEvent(data.event)
  }, [data, setCurrentEvent])

  const claims = data?.claims ?? []
  const facts = useMemo(() => claims.filter((c) => c.level !== 'opinion'), [claims])
  const unknowns = useMemo(() => claims.filter((c) => c.status === 'unverified' && c.check_worthy >= 0.6), [claims])
  const disputed = useMemo(() => claims.filter((c) => c.status === 'disputed'), [claims])

  const openDoc = (docId: string, quote: string) => setPanel({ kind: 'document', id: docId, highlight: quote })
  const stream = (title: string, url: string) => setPanel({ kind: 'agent-stream', title, url, key: `${url}-${Date.now()}` })

  const runStructured = async (label: string, fn: () => Promise<unknown>, resultKind: 'red_team' | 'normative') => {
    setBusy(label)
    try {
      const result = await fn()
      setPanel({ kind: 'agent-result', title: label, result, resultKind })
    } catch (e) {
      toast(e instanceof ApiError ? e.userMessage : String(e), 'warn')
    } finally {
      setBusy(null)
    }
  }

  const flag = async (f: 'important' | 'noise') => {
    if (!data) return
    const next = data.event.user_flag === f ? '' : f
    await api.flagEvent(id, next)
    toast(next ? (next === 'important' ? 'Marcado como importante' : 'Marcado como ruido') : 'Marca retirada')
    reload()
  }

  if (loading && !data) return <Loading text="Cargando evento…" />
  if (error) return <ErrorBox error={error} retry={reload} />
  if (!data) return null
  const ev = data.event
  const disabledTitle = agentsEnabled ? undefined : (agents?.message ?? 'Agentes desactivados: añade ANTHROPIC_API_KEY en .env')

  const tabs: Array<{ id: Tab; label: string; count?: number }> = [
    { id: 'what', label: 'Qué ha pasado', count: facts.length },
    { id: 'unknown', label: 'Lo que no sabemos', count: unknowns.length },
    { id: 'disputed', label: 'Disputadas', count: disputed.length },
    { id: 'timeline', label: 'Cronología', count: data.timeline.length },
    { id: 'sources', label: 'Fuentes', count: data.documents.length },
    { id: 'context', label: 'Contexto' },
    { id: 'impact', label: 'Impacto', count: data.exposures.length + data.prediction_markets.length },
    { id: 'forecasts', label: 'Pronósticos', count: data.questions.length },
  ]

  return (
    <div>
      <header className="event-head">
        <div className="row wrap" style={{ marginBottom: 6 }}>
          <Link to="/eventos" className="small">
            ← Eventos
          </Link>
          <ProvenanceChip titleSource={ev.title_source} />
          <span className="chip">{ev.status}</span>
          {ev.user_flag && <span className="chip accent">{ev.user_flag === 'important' ? 'importante' : 'ruido'}</span>}
          <span className="muted small mono" style={{ marginLeft: 'auto' }}>
            visto {fmtAgo(ev.first_seen_at)} · actualizado {fmtAgo(ev.last_update_at)}
          </span>
        </div>
        <h1>{ev.title_neutral}</h1>
        <div className="meta">
          <MaterialityBar value={ev.materiality} breakdown={ev.materiality_breakdown} />
          <CountryChips countries={ev.countries} max={8} />
          <DomainChip domain={ev.domain} />
          <MiniMatrix event={ev} />
          <span className="muted">
            {ev.n_sources} fuentes · {ev.n_primary} primarias · {ev.langs.join(', ') || 'sin idioma'}
          </span>
          {ev.topics.length > 0 && (
            <span className="row" style={{ gap: 3 }}>
              {ev.topics.map((t) => (
                <Chip key={t} kind="fill">
                  {t}
                </Chip>
              ))}
            </span>
          )}
        </div>
        <div className="row wrap" style={{ marginTop: 10 }}>
          <button type="button" className="btn" disabled={!agentsEnabled} title={disabledTitle} onClick={() => stream('Explícamelo en 60 s', `/api/agents/explain/${id}`)}>
            Explícamelo en 60 s
          </button>
          <button type="button" className="btn" disabled={!agentsEnabled} title={disabledTitle} onClick={() => stream('Profundiza', `/api/agents/deepen/${id}`)}>
            Profundiza
          </button>
          <span className="row" style={{ gap: 0 }}>
            <select value={tradition} onChange={(e) => setTradition(e.target.value)} aria-label="Tradición" disabled={!agentsEnabled} style={{ borderRight: 0 }}>
              {TRADITIONS.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
            <button type="button" className="btn" disabled={!agentsEnabled} title={disabledTitle} onClick={() => stream(`¿Qué diría ${tradition}?`, `/api/agents/lens?tradition=${encodeURIComponent(tradition)}&event_id=${id}`)}>
              ¿Qué diría…?
            </button>
          </span>
          <button type="button" className="btn" disabled={!agentsEnabled || busy !== null} title={disabledTitle} onClick={() => runStructured('Equipo rojo', () => api.redTeam(id), 'red_team')}>
            {busy === 'Equipo rojo' ? 'Equipo rojo…' : 'Equipo rojo'}
          </button>
          <button type="button" className="btn" disabled={!agentsEnabled || busy !== null} title={disabledTitle} onClick={() => runStructured('Traductor normativo', () => api.normative(id), 'normative')}>
            {busy === 'Traductor normativo' ? 'Traduciendo…' : 'Traductor normativo'}
          </button>
          <span className="grow" />
          <button type="button" className="btn btn-ghost btn-sm" aria-pressed={ev.user_flag === 'important'} onClick={() => flag('important')}>
            Importante
          </button>
          <button type="button" className="btn btn-ghost btn-sm" aria-pressed={ev.user_flag === 'noise'} onClick={() => flag('noise')}>
            Ruido
          </button>
          <Link to={`/prisma/${id}`} className="btn btn-ghost btn-sm">
            Prisma
          </Link>
        </div>
        {!agentsEnabled && <div className="notice warn" style={{ marginTop: 8 }}>{agents?.message ?? 'Agentes desactivados: añade ANTHROPIC_API_KEY en .env y reinicia. Las pestañas siguen funcionando con los motores deterministas.'}</div>}
      </header>

      <Tabs tabs={tabs} value={tab} onChange={setTab} />
      <div style={{ paddingTop: 'var(--sp-3)', maxWidth: 980 }}>
        {tab === 'what' && (
          <>
            {facts.length === 0 && <EmptyState title="Sin afirmaciones no opinativas">El extractor heurístico solo registra frases literales del titular y la entradilla; sin texto completo puede no haber ninguna.</EmptyState>}
            {facts.map((c) => (
              <ClaimRow key={c.id} c={c} onOpenDoc={openDoc} />
            ))}
            <p className="muted small" style={{ marginTop: 8 }}>
              Pasa el ratón por una afirmación para ver la cita literal. «Confirmada» = hay primaria (tier 1) o ≥ 2 fuentes independientes de tier ≤ 2.
            </p>
          </>
        )}
        {tab === 'unknown' && (
          <>
            {unknowns.length === 0 && <EmptyState title="Nada pendiente de verificar con prioridad alta">Aquí aparecen las afirmaciones sin verificar con check-worthiness ≥ 0,6, formuladas como preguntas abiertas.</EmptyState>}
            {unknowns.map((c) => (
              <div key={c.id} className="claim">
                <div className="side">
                  <StatusIcon status={c.status} />
                  <Level level={c.level} />
                </div>
                <div>
                  <strong>Por verificar:</strong> ¿{c.text_canonical.replace(/[.\s]+$/, '')}?
                  <div className="foot">
                    <button type="button" className="btn-link" onClick={() => openDoc(c.document_id, c.text_original ?? c.text_canonical)}>
                      {c.source_name}
                    </button>
                    <span>única fuente hasta ahora · cw {c.check_worthy.toFixed(2)}</span>
                  </div>
                </div>
              </div>
            ))}
          </>
        )}
        {tab === 'disputed' && (
          <>
            {disputed.length === 0 && <EmptyState title="Sin afirmaciones disputadas">Una afirmación pasa a «disputada» cuando hay evidencia en contra de otra fuente. Con el extractor heurístico esto es raro; el extractor con modelo detecta contradicciones.</EmptyState>}
            {disputed.map((c) => (
              <div key={c.id} style={{ borderBottom: '1px solid var(--c-line)', paddingBottom: 12, marginBottom: 12 }}>
                <ClaimRow c={c} onOpenDoc={openDoc} />
                <div className="evidence-cols">
                  <div>
                    <h4>A favor</h4>
                    {c.evidence
                      .filter((e) => e.stance === 'supports')
                      .map((e) => (
                        <div key={e.id} className="evidence supports">
                          «{e.quote}» — <button type="button" className="btn-link" onClick={() => openDoc(e.document_id, e.quote)}>{e.source_name}</button>
                        </div>
                      ))}
                  </div>
                  <div>
                    <h4>En contra</h4>
                    {c.evidence
                      .filter((e) => e.stance !== 'supports')
                      .map((e) => (
                        <div key={e.id} className="evidence contradicts">
                          «{e.quote}» — <button type="button" className="btn-link" onClick={() => openDoc(e.document_id, e.quote)}>{e.source_name}</button>
                        </div>
                      ))}
                  </div>
                </div>
              </div>
            ))}
          </>
        )}
        {tab === 'timeline' && (
          <ul className="timeline">
            {data.timeline.map((t, i) => (
              <li key={`${t.id}-${i}`} className={t.kind}>
                <div className="t">{fmtDateTime(t.t)}</div>
                {t.kind === 'document' ? (
                  <>
                    <button type="button" className="btn-link" onClick={() => openDoc(t.id, '')}>
                      {t.title}
                    </button>
                    <span className="muted">
                      {' '}
                      · {t.source}
                      {t.tier ? ` · tier ${t.tier}` : ''}
                    </span>
                  </>
                ) : (
                  <>
                    <span className="chip accent">revisión</span> {t.title}
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
        {tab === 'sources' && <SourcesTab docs={data.documents} onOpen={(d) => openDoc(d, '')} />}
        {tab === 'context' && (
          <div className="col" style={{ gap: 'var(--sp-4)' }}>
            <section>
              <h2>Actores y entidades</h2>
              <div className="row wrap" style={{ marginTop: 6 }}>
                {data.entities.map((en) => (
                  <Link key={en.id} to={`/actores/${en.id}`} className="chip" title={`${en.kind} · saliencia ${en.salience.toFixed(1)} · ${en.n} docs`}>
                    {en.name} <span className="muted">{en.n}</span>
                  </Link>
                ))}
                {data.entities.length === 0 && <span className="muted">Sin entidades del gazetteer.</span>}
              </div>
            </section>
            <section>
              <h2>Variables de estado afectadas</h2>
              {data.deltas.length === 0 && <p className="muted small">Este evento no ha movido ninguna variable de estado.</p>}
              {data.deltas.map((d) => (
                <div key={d.id} className="delta">
                  <div className="head">
                    <span className="chip mono">{d.scope}</span>
                    <span className="chip">{dimensionLabel(d.dimension)}</span>
                    <span className="mono muted small">{fmtDateTime(d.detected_at)}</span>
                  </div>
                  <div>{d.description}</div>
                </div>
              ))}
            </section>
            <section>
              <h2>Eventos relacionados</h2>
              {data.related.length === 0 && <p className="muted small">Sin eventos con entidades compartidas en 30 días.</p>}
              {data.related.map((r) => (
                <EventCard key={r.id} event={r} />
              ))}
            </section>
            <section>
              <h2>Antecedentes (Archivo)</h2>
              <p className="muted small">Análogos por similitud de embeddings locales; verificar antes de citar.</p>
              {data.analogs.cases.length > 0 && (
                <>
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Caso</th>
                        <th>Categoría</th>
                        <th>Periodo</th>
                        <th className="num">Similitud</th>
                        <th>Desenlace</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.analogs.cases.map((c) => (
                        <tr key={c.id} className="clickable" onClick={() => nav(`/archivo?caso=${c.id}`)}>
                          <td>{c.name}</td>
                          <td>{c.category}</td>
                          <td className="mono">
                            {c.start_date?.slice(0, 4)}–{c.end_date?.slice(0, 4) ?? '…'}
                          </td>
                          <td className="num">{c.similarity?.toFixed(3)}</td>
                          <td>{c.outcome}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {data.analogs.compare && <CompareTable compare={data.analogs.compare} />}
                </>
              )}
            </section>
          </div>
        )}
        {tab === 'impact' && (
          <div className="col" style={{ gap: 'var(--sp-4)' }}>
            <div className="notice">Información, no asesoramiento financiero. ATLAS nunca emite órdenes de compra o venta.</div>
            <section>
              <h2>Exposición de tus negocios</h2>
              {data.exposures.length === 0 && <p className="muted small">Ninguna alerta de exposición activa para este evento.</p>}
              {data.exposures.map((x) => (
                <div key={x.id} className="alert-row">
                  <div>
                    <strong>{x.business_name}</strong> · canal {channelLabel(x.channel)} · confianza <span className="num">{fmtPct(x.confidence)}</span>
                    <div className="muted">{x.explanation}</div>
                  </div>
                  <Link to="/mando" className="small">
                    Mando
                  </Link>
                </div>
              ))}
            </section>
            <section>
              <h2>Mercados de predicción relacionados</h2>
              {data.prediction_markets.length === 0 && <p className="muted small">Ningún mercado con solapamiento léxico suficiente (≥ 2 términos).</p>}
              {data.prediction_markets.length > 0 && (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Pregunta</th>
                      <th>Sede</th>
                      <th className="num">Prob.</th>
                      <th className="num">Volumen</th>
                      <th className="num">Solap.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.prediction_markets.map((m) => (
                      <tr key={m.id}>
                        <td>
                          <ExtLink href={m.url}>{m.question}</ExtLink>
                        </td>
                        <td>{m.venue}</td>
                        <td className="num">{fmtPct(m.probability)}</td>
                        <td className="num">{fmtVolume(m.volume)}</td>
                        <td className="num">{m.overlap}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
          </div>
        )}
        {tab === 'forecasts' && (
          <div className="col">
            <div>
              <Link to={`/pronosticos?nuevo=1&evento=${id}`} className="btn btn-primary">
                Hacer pronóstico sobre este evento
              </Link>
            </div>
            {data.questions.length === 0 && <p className="muted small">Todavía no hay preguntas de pronóstico originadas en este evento.</p>}
            {data.questions.map((q) => {
              const entries = Object.entries(q.latest)
              return (
                <Card key={q.id} title={<Link to={`/pronosticos/${q.id}`}>{q.title}</Link>} extra={<span className="chip">{q.status}</span>}>
                  <div className="pbars">
                    {entries.length === 0 && <span className="muted">Sin pronósticos todavía.</span>}
                    {entries.map(([f, p]) => (
                      <div key={f} style={{ display: 'contents' }}>
                        <span>{f === 'user' ? 'Tú' : f}</span>
                        <span className={`bar ${f === 'user' ? 'user' : f.startsWith('market') ? 'market' : 'system'}`}>
                          <i style={{ width: `${p * 100}%` }} />
                        </span>
                        <span className="num right">{fmtPct(p)}</span>
                      </div>
                    ))}
                  </div>
                  <div className="muted small" style={{ marginTop: 4 }}>
                    cierra {fmtDateTime(q.close_at)}
                  </div>
                </Card>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

function CompareTable({ compare }: { compare: NonNullable<EventDetailT['analogs']['compare']> }) {
  return (
    <table className="table" style={{ marginTop: 8 }}>
      <thead>
        <tr>
          <th>Variable</th>
          {compare.outcomes.map((o) => (
            <th key={o.name}>{o.name}</th>
          ))}
          <th>Coinciden</th>
        </tr>
      </thead>
      <tbody>
        {compare.variables.map((v) => (
          <tr key={v.variable}>
            <td>{v.variable}</td>
            {v.values.map((x, i) => (
              <td key={i} className="mono">
                {x == null ? '—' : String(x)}
              </td>
            ))}
            <td>{v.agree ? 'sí' : 'no'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function SourcesTab({ docs, onOpen }: { docs: EventDetailT['documents']; onOpen: (id: string) => void }) {
  const [groupBy, setGroupBy] = useState<'type' | 'ideology' | 'lang'>('type')
  const groups = useMemo(() => {
    const g = new Map<string, typeof docs>()
    for (const d of docs) {
      const k = groupBy === 'type' ? sourceTypeLabel(d.source_type) : groupBy === 'ideology' ? ideologyLabel(d.ideology_label) : (d.lang ?? 'sin idioma')
      g.set(k, [...(g.get(k) ?? []), d])
    }
    return Array.from(g.entries()).sort((a, b) => b[1].length - a[1].length)
  }, [docs, groupBy])
  return (
    <div>
      <div className="filters">
        <span className="label">Agrupar por</span>
        <div className="seg">
          <button type="button" aria-pressed={groupBy === 'type'} onClick={() => setGroupBy('type')}>
            Tipo
          </button>
          <button type="button" aria-pressed={groupBy === 'ideology'} onClick={() => setGroupBy('ideology')}>
            Ecosistema
          </button>
          <button type="button" aria-pressed={groupBy === 'lang'} onClick={() => setGroupBy('lang')}>
            Idioma
          </button>
        </div>
      </div>
      {groups.map(([k, list]) => (
        <section key={k} style={{ marginBottom: 12 }}>
          <h4 style={{ marginBottom: 4 }}>
            {k} <span className="muted">({list.length})</span>
          </h4>
          <table className="table">
            <tbody>
              {list.map((d) => (
                <tr key={d.id}>
                  <td style={{ width: 160 }}>
                    <strong>{d.source_name}</strong>
                    <div className="muted small">
                      tier {d.tier} · {sourceTypeLabel(d.source_type)}
                    </div>
                  </td>
                  <td>
                    <button type="button" className="btn-link" onClick={() => onOpen(d.id)} style={{ textAlign: 'left' }}>
                      {d.title}
                    </button>
                    <div className="muted small row wrap">
                      <span>{ideologyLabel(d.ideology_label)}</span>
                      <span>{blocLabel(d.region_bloc)}</span>
                      <span>{stateRelationLabel(d.state_relation)}</span>
                      <span>{paywallLabel(d.paywall)}</span>
                      <span className="mono">{d.lang}</span>
                    </div>
                  </td>
                  <td className="mono muted small" style={{ whiteSpace: 'nowrap' }}>
                    {fmtDateTime(d.published_at)}
                  </td>
                  <td>
                    <ExtLink href={d.url}>original ↗</ExtLink>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </div>
  )
}
