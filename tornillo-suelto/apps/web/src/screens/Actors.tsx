import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { Actor, ActorDetail } from '../api/types'
import { Card, EmptyState, ErrorBox, ExtLink, Level, Loading, StatusIcon } from '../components/ui/basics'
import { DataTable } from '../components/ui/DataTable'
import { EventCard } from '../components/ui/EventCard'
import { fmtDateTime, isoDateLocal, parseDate } from '../lib/format'
import { useAsync, useDebounced } from '../lib/hooks'
import { useStore } from '../state/store'
import './screens.css'

const KIND_LABEL: Record<string, string> = { country: 'País', institution: 'Institución', company: 'Empresa', concept: 'Concepto', person: 'Persona' }

function MentionsChart({ docs, days = 30 }: { docs: ActorDetail['documents']; days?: number }) {
  const series = useMemo(() => {
    const counts = new Map<string, number>()
    const today = new Date()
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(today)
      d.setDate(today.getDate() - i)
      counts.set(isoDateLocal(d), 0)
    }
    for (const doc of docs) {
      const d = parseDate(doc.published_at ?? doc.fetched_at)
      if (!d) continue
      const k = isoDateLocal(d)
      if (counts.has(k)) counts.set(k, (counts.get(k) ?? 0) + 1)
    }
    return Array.from(counts.entries())
  }, [docs, days])
  const max = Math.max(1, ...series.map(([, v]) => v))
  const w = 600
  const h = 80
  const bw = w / series.length
  return (
    <svg viewBox={`0 0 ${w} ${h + 16}`} className="graph-svg" role="img" aria-label="Menciones por día">
      {series.map(([day, v], i) => (
        <g key={day}>
          <rect x={i * bw + 1} y={h - (v / max) * (h - 4)} width={Math.max(1, bw - 2)} height={(v / max) * (h - 4)} fill={v ? 'var(--c-black)' : 'var(--c-line)'}>
            <title>
              {day}: {v}
            </title>
          </rect>
          {i % 5 === 0 && (
            <text x={i * bw + 1} y={h + 12} fontSize="9" fill="var(--c-muted)" fontFamily="var(--font-mono)">
              {day.slice(5)}
            </text>
          )}
        </g>
      ))}
    </svg>
  )
}

function CoMentions({ center, items }: { center: string; items: ActorDetail['co_mentions'] }) {
  const nav = useNavigate()
  const w = 520
  const h = 320
  const cx = w / 2
  const cy = h / 2
  const max = Math.max(1, ...items.map((i) => i.n))
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="graph-svg" role="img" aria-label="Red de co-menciones">
      {items.map((it, i) => {
        const a = (i / items.length) * Math.PI * 2 - Math.PI / 2
        const r = 110 + (i % 2) * 25
        const x = cx + Math.cos(a) * r
        const y = cy + Math.sin(a) * r
        return (
          <g key={it.id} className="node" style={{ cursor: 'pointer' }} onClick={() => nav(`/actores/${it.id}`)}>
            <line x1={cx} y1={cy} x2={x} y2={y} stroke="var(--c-muted)" strokeWidth={0.6 + (it.n / max) * 3} />
            <circle cx={x} cy={y} r={5 + (it.n / max) * 8} fill="var(--c-accent)" stroke="var(--c-black)" />
            <text x={x} y={y + 22} textAnchor="middle" fontSize="10" fill="var(--c-text)">
              {it.name.length > 18 ? `${it.name.slice(0, 17)}…` : it.name}
            </text>
            <title>
              {it.name} · {it.n} documentos en común
            </title>
          </g>
        )
      })}
      <circle cx={cx} cy={cy} r={16} fill="var(--c-black)" />
      <text x={cx} y={cy + 32} textAnchor="middle" fontSize="11" fontWeight="700" fill="var(--c-text)">
        {center}
      </text>
    </svg>
  )
}

function ActorSheet({ id }: { id: string }) {
  const { data, error, loading } = useAsync<ActorDetail>(() => api.actor(id), [id])
  const { setCurrentEvent, setPanel } = useStore()
  if (loading && !data) return <Loading />
  if (error) return <ErrorBox error={error} />
  if (!data) return null
  const e = data.entity
  return (
    <div>
      <div className="screen-head">
        <div>
          <div className="row wrap small">
            <Link to="/actores">← Actores</Link>
            <span className="chip">{KIND_LABEL[e.kind] ?? e.kind}</span>
            {e.country && (
              <Link to={`/paises/${e.country}`} className="chip mono">
                {e.country}
              </Link>
            )}
            {e.wikidata_qid && <ExtLink href={`https://www.wikidata.org/wiki/${e.wikidata_qid}`}>{e.wikidata_qid}</ExtLink>}
          </div>
          <h1>{e.name}</h1>
          {e.aliases.length > 0 && <div className="sub">también: {e.aliases.join(', ')}</div>}
          {e.description && <div className="sub">{e.description}</div>}
        </div>
        <div className="muted small">{e.mentions_7d} menciones en 7 d</div>
      </div>
      <div className="two-col">
        <section className="section" style={{ marginTop: 0 }}>
          <h2>Menciones por día (30 d)</h2>
          <MentionsChart docs={data.documents} />
        </section>
        <section className="section" style={{ marginTop: 0 }}>
          <h2>Co-menciones</h2>
          {data.co_mentions.length ? <CoMentions center={e.name} items={data.co_mentions} /> : <p className="muted small">Sin co-menciones en 30 días.</p>}
        </section>
      </div>
      <div className="two-col">
        <section className="section">
          <h2>Afirmaciones atribuidas</h2>
          {data.attributed_claims.length === 0 && <p className="muted small">Ninguna afirmación atribuida por patrón («según X», «X dijo»).</p>}
          {data.attributed_claims.map((c) => (
            <div key={c.id} style={{ padding: '6px 0', borderBottom: '1px solid var(--c-line)', fontSize: 'var(--fs-data)' }}>
              <div className="row wrap" style={{ marginBottom: 2 }}>
                <StatusIcon status={c.status} />
                <Level level={c.level} />
                <span className="muted mono">{fmtDateTime(c.first_seen_at)}</span>
              </div>
              <div>{c.text_canonical}</div>
              <div className="muted small">
                {c.source_name} · <ExtLink href={c.url}>original ↗</ExtLink>
              </div>
            </div>
          ))}
        </section>
        <section className="section">
          <h2>Eventos</h2>
          {data.events.length === 0 && <p className="muted small">Sin eventos asociados.</p>}
          {data.events.map((ev) => (
            <EventCard key={ev.id} event={ev} onSelect={setCurrentEvent} />
          ))}
        </section>
      </div>
      <section className="section">
        <h2>Documentos recientes</h2>
        <DataTable
          rows={data.documents.slice(0, 40)}
          rowKey={(d) => d.id}
          onRow={(d) => setPanel({ kind: 'document', id: d.id })}
          columns={[
            { key: 't', label: 'Fecha', render: (d) => <span className="mono">{fmtDateTime(d.published_at)}</span>, sort: (d) => d.published_at ?? '', width: 110 },
            { key: 's', label: 'Fuente', render: (d) => d.source_name, sort: (d) => d.source_name ?? '', width: 160 },
            { key: 'title', label: 'Título', render: (d) => d.title },
            { key: 'sal', label: 'Saliencia', num: true, render: (d) => d.salience?.toFixed(2) ?? '—', sort: (d) => d.salience ?? 0, width: 80 },
          ]}
        />
      </section>
    </div>
  )
}

export default function Actors() {
  const { id } = useParams()
  const nav = useNavigate()
  const [q, setQ] = useState('')
  const [kind, setKind] = useState('')
  const dq = useDebounced(q, 250)
  const { data, error, loading } = useAsync<{ actors: Actor[] }>(() => api.actors({ q: dq || undefined, kind: kind || undefined, limit: 80 }), [dq, kind])
  if (id) return <ActorSheet id={id} />
  return (
    <div>
      <div className="screen-head">
        <div>
          <h1>Actores</h1>
          <div className="sub">Personas, instituciones, empresas y conceptos del gazetteer, con menciones fechadas.</div>
        </div>
        <div className="tools">
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar actor…" aria-label="Buscar actor" />
          <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Tipo">
            <option value="">Todos los tipos</option>
            {Object.entries(KIND_LABEL).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </div>
      </div>
      {loading && !data && <Loading />}
      <ErrorBox error={error} />
      {data && data.actors.length === 0 && <EmptyState title="Sin actores">Nada coincide con la búsqueda.</EmptyState>}
      {data && data.actors.length > 0 && (
        <Card className="flat">
          <DataTable
            rows={data.actors}
            rowKey={(a) => a.id}
            onRow={(a) => nav(`/actores/${a.id}`)}
            columns={[
              { key: 'name', label: 'Nombre', render: (a) => <strong>{a.name}</strong>, sort: (a) => a.name },
              { key: 'kind', label: 'Tipo', render: (a) => KIND_LABEL[a.kind] ?? a.kind, sort: (a) => a.kind, width: 120 },
              { key: 'country', label: 'País', render: (a) => <span className="mono">{a.country ?? '—'}</span>, width: 60 },
              { key: 'm', label: 'Menciones 7 d', num: true, render: (a) => a.mentions_7d, sort: (a) => a.mentions_7d, width: 120 },
              { key: 'qid', label: 'Wikidata', render: (a) => (a.wikidata_qid ? <ExtLink href={`https://www.wikidata.org/wiki/${a.wikidata_qid}`}>{a.wikidata_qid}</ExtLink> : <span className="muted">—</span>), width: 100 },
            ]}
          />
        </Card>
      )}
    </div>
  )
}
