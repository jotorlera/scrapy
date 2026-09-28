import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { streamPost, type StreamHandle } from '../api/sse'
import type { ArgumentMap, EventSummary, Genealogy } from '../api/types'
import { AgentStream } from '../components/ui/AgentStream'
import { Card, EmptyState, ErrorBox, Loading, Tabs } from '../components/ui/basics'
import { Markdown } from '../components/ui/Markdown'
import { Modal } from '../components/ui/Modal'
import { fmtDate } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { TRADITIONS } from '../lib/labels'
import { useStore } from '../state/store'
import './screens.css'

type Tab = 'mapas' | 'genealogia' | 'lentes' | 'tutor'

/* ───────── Mapas argumentales ───────── */
function MapsTab() {
  const nav = useNavigate()
  const { data, error, loading, reload } = useAsync<{ maps: ArgumentMap[] }>(() => api.maps(), [])
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [topic, setTopic] = useState('')
  const create = async () => {
    if (!title.trim()) return
    const r = await api.createMap({ title: title.trim(), topic: topic.trim() || undefined })
    setOpen(false)
    reload()
    nav(`/agora/mapas/${r.id}`)
  }
  return (
    <div>
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
        <p className="muted small" style={{ margin: 0 }}>
          Nodos tipados (tesis, premisa, objeción, réplica, evidencia, autor, obra) y aristas de apoyo o ataque. El análisis detecta premisas sin apoyo, objeciones sin respuesta y circularidad.
        </p>
        <button type="button" className="btn btn-primary" onClick={() => setOpen(true)}>
          Nuevo mapa
        </button>
      </div>
      {loading && <Loading />}
      <ErrorBox error={error} />
      {data && data.maps.length === 0 && <EmptyState title="Sin mapas">Crea el primero o ejecuta `atlas seed` para sembrar el mapa de la renta básica.</EmptyState>}
      <div className="biz-cards">
        {data?.maps.map((m) => (
          <Card key={m.id} title={<Link to={`/agora/mapas/${m.id}`}>{m.title}</Link>} extra={<span className="muted small mono">{m.n_nodes ?? 0} nodos</span>}>
            <div className="muted small">
              {m.topic ?? 'sin tema'} · creado {fmtDate(m.created_at)}
            </div>
          </Card>
        ))}
      </div>
      <Modal open={open} title="Nuevo mapa argumental" onClose={() => setOpen(false)}>
        <div className="col">
          <label className="field">
            Título
            <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="¿Es legítima la renta básica universal?" />
          </label>
          <label className="field">
            Tema (opcional)
            <input type="text" value={topic} onChange={(e) => setTopic(e.target.value)} />
          </label>
          <div className="row" style={{ justifyContent: 'flex-end' }}>
            <button type="button" className="btn btn-primary" onClick={create} disabled={!title.trim()}>
              Crear
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

/* ───────── Genealogía de la libertad ───────── */
function yearOf(years: string): number {
  const m = /^(\d{4})/.exec(years)
  return m ? Number(m[1]) : 1900
}

function GenealogyTab() {
  const { data, error, loading } = useAsync<Genealogy>(() => api.genealogy(), [])
  const [sel, setSel] = useState<string | null>(null)
  const layout = useMemo(() => {
    if (!data) return null
    const years = data.nodes.map((n) => yearOf(n.years))
    const minY = Math.min(...years) - 20
    const maxY = Math.max(...years) + 40
    const w = 1100
    const h = 420
    const pad = 60
    const x = (y: number) => pad + ((y - minY) / (maxY - minY)) * (w - 2 * pad)
    // filas alternas para evitar solapes: ordenar por año y repartir en 5 carriles
    const sorted = data.nodes.slice().sort((a, b) => yearOf(a.years) - yearOf(b.years))
    const lanes = 5
    const pos = new Map<string, { x: number; y: number }>()
    sorted.forEach((n, i) => pos.set(n.id, { x: x(yearOf(n.years)), y: 50 + (i % lanes) * ((h - 110) / (lanes - 1)) }))
    const ticks: number[] = []
    for (let y = Math.ceil(minY / 50) * 50; y <= maxY; y += 50) ticks.push(y)
    return { w, h, pos, x, ticks }
  }, [data])
  if (loading) return <Loading />
  if (error) return <ErrorBox error={error} />
  if (!data || !layout) return null
  const selected = data.nodes.find((n) => n.id === sel)
  return (
    <div className="genealogy">
      <h2 style={{ marginBottom: 6 }}>{data.title}</h2>
      <p className="muted small">Eje horizontal: año de nacimiento. Las aristas llevan el tipo de relación (influencia, crítica, reacción…); pasa el ratón para verlo. Clic en un autor para leer su concepto.</p>
      <svg viewBox={`0 0 ${layout.w} ${layout.h}`} role="img" aria-label="Genealogía del concepto de libertad">
        <g className="axis">
          {layout.ticks.map((t) => (
            <g key={t}>
              <line x1={layout.x(t)} x2={layout.x(t)} y1={20} y2={layout.h - 30} />
              <text x={layout.x(t)} y={layout.h - 14} textAnchor="middle">
                {t}
              </text>
            </g>
          ))}
        </g>
        {data.edges.map(([a, b, rel], i) => {
          const pa = layout.pos.get(a)
          const pb = layout.pos.get(b)
          if (!pa || !pb) return null
          const mx = (pa.x + pb.x) / 2
          return (
            <path key={i} className="gedge" d={`M${pa.x + 45},${pa.y} C${mx},${pa.y} ${mx},${pb.y} ${pb.x - 45},${pb.y}`}>
              <title>
                {a} → {b}: {rel}
              </title>
            </path>
          )
        })}
        {data.nodes.map((n) => {
          const p = layout.pos.get(n.id)!
          return (
            <g key={n.id} className="gnode" transform={`translate(${p.x - 45},${p.y - 14})`} style={{ cursor: 'pointer' }} onClick={() => setSel(n.id)} tabIndex={0} role="button" aria-label={n.label} onKeyDown={(e) => e.key === 'Enter' && setSel(n.id)}>
              <rect width={90} height={28} fill={sel === n.id ? 'var(--c-accent)' : undefined} />
              <text x={45} y={18} textAnchor="middle" fill={sel === n.id ? '#000' : undefined}>
                {n.label}
              </text>
            </g>
          )
        })}
      </svg>
      {selected && (
        <Card title={`${selected.label} (${selected.years})`} style={{ marginTop: 8, maxWidth: 720 }}>
          <div className="read">
            <div>
              <span className="label">Obra</span> {selected.work}
            </div>
            <div>
              <span className="label">Concepto</span> {selected.concept}
            </div>
            <div className="small muted" style={{ marginTop: 6 }}>
              Relaciones: {data.edges.filter(([a, b]) => a === selected.id || b === selected.id).map(([a, b, rel]) => `${a === selected.id ? '→ ' + b : '← ' + a} (${rel})`).join(' · ')}
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}

/* ───────── Lentes ───────── */
function LensTab() {
  const { agentsEnabled, agents } = useStore()
  const [tradition, setTradition] = useState(TRADITIONS[0])
  const [text, setText] = useState('')
  const [eventId, setEventId] = useState('')
  const [events, setEvents] = useState<EventSummary[]>([])
  const [run, setRun] = useState<{ url: string; key: string } | null>(null)
  useEffect(() => {
    api.events({ hours: 168, limit: 40 }).then((r) => setEvents(r.events)).catch(() => undefined)
  }, [])
  const launch = () => {
    const p = new URLSearchParams({ tradition })
    if (eventId) p.set('event_id', eventId)
    else if (text.trim()) p.set('text', text.trim())
    else return
    setRun({ url: `/api/agents/lens?${p.toString()}`, key: String(Date.now()) })
  }
  return (
    <div className="two-col narrow-left">
      <Card title="¿Cómo lo interpretaría…?">
        <div className="col">
          <label className="field">
            Tradición o autor
            <select value={tradition} onChange={(e) => setTradition(e.target.value)}>
              {TRADITIONS.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </label>
          <label className="field">
            Evento (opcional)
            <select value={eventId} onChange={(e) => setEventId(e.target.value)}>
              <option value="">— texto libre —</option>
              {events.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.title_neutral.slice(0, 90)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Texto libre
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={5} disabled={!!eventId} placeholder="Pega un pasaje, una tesis o una noticia…" />
          </label>
          <button type="button" className="btn btn-primary" onClick={launch} disabled={!agentsEnabled || (!eventId && !text.trim())} title={agentsEnabled ? undefined : (agents?.message ?? undefined)}>
            Aplicar la lente
          </button>
          {!agentsEnabled && <div className="notice warn">{agents?.message ?? 'Agentes desactivados: añade ANTHROPIC_API_KEY en .env.'}</div>}
          <p className="muted small">Cada lente se marca como reconstrucción y cita obras concretas; termina con la mejor objeción desde otra tradición.</p>
        </div>
      </Card>
      <div>{run ? <AgentStream title={`Lente · ${tradition}`} url={run.url} runKey={run.key} /> : <EmptyState title="Sin lente aplicada">Elige tradición y evento o texto, y pulsa «Aplicar la lente».</EmptyState>}</div>
    </div>
  )
}

/* ───────── Tutor socrático ───────── */
type ChatMode = 'socratic' | 'sparring' | 'exam' | 'turing'
const MODE_LABEL: Record<ChatMode, string> = { socratic: 'Socrático', sparring: 'Sparring', exam: 'Examen', turing: 'Test de Turing' }
const MODE_DESC: Record<ChatMode, string> = {
  socratic: 'El tutor pregunta en lugar de responder.',
  sparring: 'Debate contra la reconstrucción de un autor o tradición, con obras reales.',
  exam: '10 minutos defendiendo una tesis contra objeciones crecientes; rúbrica al final.',
  turing: 'Escribe la posición contraria; el sistema evalúa si un defensor real la firmaría.',
}

function SocraticTab({ initialTopic }: { initialTopic: string | null }) {
  const { agentsEnabled, agents, toast } = useStore()
  const [mode, setMode] = useState<ChatMode>('socratic')
  const [history, setHistory] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([])
  const [input, setInput] = useState(initialTopic ? `Quiero examinar mi posición sobre: ${initialTopic}` : '')
  const [streaming, setStreaming] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const handle = useRef<StreamHandle | null>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const [cardsOpen, setCardsOpen] = useState(false)
  const [cardDrafts, setCardDrafts] = useState<Array<{ front: string; back: string }>>([])

  useEffect(() => endRef.current?.scrollIntoView({ block: 'end' }), [history, streaming])
  useEffect(() => () => handle.current?.close(), [])

  const send = () => {
    const msg = input.trim()
    if (!msg || busy) return
    const hist = history
    setHistory((h) => [...h, { role: 'user', content: msg }])
    setInput('')
    setStreaming('')
    setError(null)
    setBusy(true)
    let acc = ''
    handle.current = streamPost(
      '/api/agents/socratic',
      { mode, message: msg, history: hist },
      {
        onEvent: (ev) => {
          if (ev.type === 'delta') {
            acc += ev.text
            setStreaming(acc)
          } else if (ev.type === 'done') {
            const full = ev.text || acc
            setHistory((h) => [...h, { role: 'assistant', content: full }])
            setStreaming('')
          } else if (ev.type === 'error') setError(ev.message)
        },
        onClose: () => setBusy(false),
      },
    )
  }

  const proposeCards = () => {
    const drafts: Array<{ front: string; back: string }> = []
    for (let i = 0; i < history.length - 1; i++) {
      if (history[i].role === 'assistant' && history[i + 1].role === 'user') {
        const q = history[i].content.split('\n').find((l) => l.includes('?')) ?? history[i].content.slice(0, 160)
        drafts.push({ front: q.trim().slice(0, 240), back: history[i + 1].content.trim().slice(0, 500) })
      }
    }
    if (!drafts.length) drafts.push({ front: '', back: '' })
    setCardDrafts(drafts)
    setCardsOpen(true)
  }
  const saveCards = async () => {
    let n = 0
    for (const d of cardDrafts) {
      if (d.front.trim() && d.back.trim()) {
        await api.createCard({ front: d.front, back: d.back, source_ref: { kind: 'socratic', mode } })
        n++
      }
    }
    setCardsOpen(false)
    toast(`${n} tarjeta(s) de repaso creadas en el TALLER`)
  }

  return (
    <div>
      <div className="filters">
        <div className="seg" role="group" aria-label="Modo del tutor">
          {(Object.keys(MODE_LABEL) as ChatMode[]).map((m) => (
            <button key={m} type="button" aria-pressed={mode === m} onClick={() => setMode(m)}>
              {MODE_LABEL[m]}
            </button>
          ))}
        </div>
        <span className="muted small">{MODE_DESC[mode]}</span>
        <span className="grow" />
        <button type="button" className="btn btn-ghost btn-sm" onClick={proposeCards} disabled={history.length < 2}>
          Crear tarjetas de repaso
        </button>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => {
            handle.current?.close()
            setHistory([])
            setStreaming('')
          }}
          disabled={!history.length}
        >
          Nueva sesión
        </button>
      </div>
      {!agentsEnabled && <div className="notice warn" style={{ marginBottom: 8 }}>{agents?.message ?? 'Agentes desactivados: añade ANTHROPIC_API_KEY en .env y reinicia.'} El tutor necesita el modelo; el resto del Ágora (mapas, genealogía) funciona sin clave.</div>}
      <div className="chat">
        {history.length === 0 && !streaming && <div className="muted small">Plantea una tesis o una duda. El tutor no responde: pregunta. Al final, convierte el diálogo en tarjetas de repaso.</div>}
        {history.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="who">{m.role === 'user' ? 'Tú' : `Tutor · ${MODE_LABEL[mode]}`}</div>
            <Markdown text={m.content} />
          </div>
        ))}
        {streaming && (
          <div className="msg assistant">
            <div className="who">Tutor · escribiendo</div>
            <Markdown text={streaming} />
          </div>
        )}
        {error && <div className="errorbox">{error}</div>}
        <div ref={endRef} />
        <div className="row" style={{ alignItems: 'flex-end' }}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            rows={3}
            className="grow"
            placeholder={mode === 'turing' ? 'Escribe la posición contraria a la tuya como la defendería su mejor defensor…' : 'Tu tesis, tu duda o tu respuesta…'}
            aria-label="Mensaje"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) send()
            }}
          />
          <button type="button" className="btn btn-primary" onClick={send} disabled={!agentsEnabled || busy || !input.trim()}>
            {busy ? 'Pensando…' : 'Enviar'}
          </button>
        </div>
        <div className="muted small">⌘/Ctrl + Enter envía. Salida de modelo: reconstrucción, no autoridad.</div>
      </div>
      <Modal open={cardsOpen} title="Tarjetas de repaso a partir del diálogo" onClose={() => setCardsOpen(false)} wide>
        <div className="col">
          {cardDrafts.map((d, i) => (
            <div key={i} className="two-col">
              <label className="field">
                Pregunta
                <textarea rows={3} value={d.front} onChange={(e) => setCardDrafts((c) => c.map((x, j) => (j === i ? { ...x, front: e.target.value } : x)))} />
              </label>
              <label className="field">
                Respuesta
                <textarea rows={3} value={d.back} onChange={(e) => setCardDrafts((c) => c.map((x, j) => (j === i ? { ...x, back: e.target.value } : x)))} />
              </label>
            </div>
          ))}
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <button type="button" className="btn btn-ghost" onClick={() => setCardDrafts((c) => [...c, { front: '', back: '' }])}>
              Añadir tarjeta
            </button>
            <button type="button" className="btn btn-primary" onClick={saveCards}>
              Guardar en el TALLER
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default function Agora() {
  const [params, setParams] = useSearchParams()
  const tab = (params.get('tab') as Tab) || 'mapas'
  const tema = params.get('tema')
  const setTab = (t: Tab) => {
    const p = new URLSearchParams(params)
    p.set('tab', t)
    setParams(p, { replace: true })
  }
  return (
    <div>
      <div className="screen-head">
        <div>
          <h1>Ágora</h1>
          <div className="sub">La capa que da sentido al resto: argumentos, genealogías, lentes y un tutor que pregunta.</div>
        </div>
      </div>
      <Tabs
        tabs={[
          { id: 'mapas', label: 'Mapas argumentales' },
          { id: 'genealogia', label: 'Genealogía de la libertad' },
          { id: 'lentes', label: 'Lentes' },
          { id: 'tutor', label: 'Tutor socrático' },
        ]}
        value={tab}
        onChange={setTab}
      />
      <div style={{ paddingTop: 'var(--sp-3)' }}>
        {tab === 'mapas' && <MapsTab />}
        {tab === 'genealogia' && <GenealogyTab />}
        {tab === 'lentes' && <LensTab />}
        {tab === 'tutor' && <SocraticTab initialTopic={tema} />}
      </div>
    </div>
  )
}
