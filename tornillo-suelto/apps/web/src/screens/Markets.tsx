import { useMemo, useState } from 'react'
import { api } from '../api/client'
import type { CausalChannel, MarketsResponse } from '../api/types'
import { Card, EmptyState, ErrorBox, ExtLink, Loading, Sparkline } from '../components/ui/basics'
import { fmtDateTime, fmtPct, fmtPrice, fmtSignedPct, fmtVolume } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { useStore } from '../state/store'
import './screens.css'

const GROUP_LABEL: Record<string, string> = { indices: 'Índices', fx: 'Divisas', commodities: 'Materias primas', rates: 'Tipos', crypto: 'Cripto' }
const GROUP_ORDER = ['indices', 'fx', 'commodities', 'rates', 'crypto']

const NODE_LABEL: Record<string, string> = {
  brent_price: 'Precio del Brent',
  headline_inflation_importers: 'Inflación general (importadores)',
  headline_inflation: 'Inflación general',
  policy_rate_expectations: 'Expectativas de tipos',
  growth_equity_valuations: 'Valoración de acciones de crecimiento',
}
const nodeLabel = (k: string) => NODE_LABEL[k] ?? k.replace(/_/g, ' ')

/** Grafo dirigido por capas (Kahn) de los canales causales; SVG propio, sin dependencias. */
function CausalGraph({ channels }: { channels: CausalChannel[] }) {
  const layout = useMemo(() => {
    const nodes = Array.from(new Set(channels.flatMap((c) => [c.from, c.to])))
    const indeg = new Map(nodes.map((n) => [n, 0]))
    for (const c of channels) indeg.set(c.to, (indeg.get(c.to) ?? 0) + 1)
    const layer = new Map<string, number>()
    let frontier = nodes.filter((n) => (indeg.get(n) ?? 0) === 0)
    let l = 0
    const seen = new Set<string>()
    while (frontier.length) {
      for (const n of frontier) {
        layer.set(n, l)
        seen.add(n)
      }
      const next = new Set<string>()
      for (const c of channels) if (seen.has(c.from) && !seen.has(c.to)) next.add(c.to)
      frontier = Array.from(next).filter((n) => channels.filter((c) => c.to === n).every((c) => seen.has(c.from) || (layer.get(c.from) ?? 99) < 99))
      l++
      if (l > 20) break
    }
    for (const n of nodes) if (!layer.has(n)) layer.set(n, l)
    const byLayer = new Map<number, string[]>()
    for (const [n, li] of layer) byLayer.set(li, [...(byLayer.get(li) ?? []), n])
    const colW = 230
    const rowH = 54
    const pos = new Map<string, { x: number; y: number }>()
    let maxRows = 1
    for (const [li, ns] of byLayer) {
      maxRows = Math.max(maxRows, ns.length)
      ns.forEach((n, i) => pos.set(n, { x: 20 + li * colW, y: 20 + i * rowH }))
    }
    const width = 40 + (byLayer.size || 1) * colW
    const height = 40 + maxRows * rowH
    return { pos, width, height }
  }, [channels])

  return (
    <svg className="graph-svg" viewBox={`0 0 ${layout.width} ${layout.height}`} role="img" aria-label="Grafo de canales causales">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" fill="var(--c-black)" />
        </marker>
        <marker id="arrow-neg" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" fill="var(--c-warn)" />
        </marker>
      </defs>
      {channels.map((c, i) => {
        const a = layout.pos.get(c.from)
        const b = layout.pos.get(c.to)
        if (!a || !b) return null
        const x1 = a.x + 190
        const y1 = a.y + 18
        const x2 = b.x
        const y2 = b.y + 18
        const neg = c.sign.includes('−') || c.sign.includes('-')
        const mx = (x1 + x2) / 2
        return (
          <g key={i}>
            <path className={`edge ${neg ? 'neg' : ''}`} d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`} markerEnd={neg ? 'url(#arrow-neg)' : 'url(#arrow)'}>
              <title>
                {nodeLabel(c.from)} → {nodeLabel(c.to)} ({c.sign}, {c.lag ?? 'sin desfase'}) {c.ref ? `· ${c.ref}` : ''}
              </title>
            </path>
            <text className="edge-label" x={mx} y={(y1 + y2) / 2 - 4} textAnchor="middle">
              {c.sign} {c.lag ?? ''}
            </text>
          </g>
        )
      })}
      {Array.from(layout.pos.entries()).map(([n, p]) => (
        <g key={n} className="node" transform={`translate(${p.x},${p.y})`}>
          <rect width={190} height={36} />
          <text x={8} y={22}>
            {nodeLabel(n).length > 30 ? `${nodeLabel(n).slice(0, 29)}…` : nodeLabel(n)}
            <title>{nodeLabel(n)}</title>
          </text>
        </g>
      ))}
    </svg>
  )
}

export default function Markets() {
  const { data, error, loading, reload } = useAsync<MarketsResponse>(() => api.markets(), [])
  const { toast } = useStore()
  const [pmFilter, setPmFilter] = useState('')
  const groups = useMemo(() => {
    const g = new Map<string, MarketsResponse['quotes']>()
    for (const q of data?.quotes ?? []) g.set(q.group_name, [...(g.get(q.group_name) ?? []), q])
    return Array.from(g.entries()).sort((a, b) => GROUP_ORDER.indexOf(a[0]) - GROUP_ORDER.indexOf(b[0]))
  }, [data])
  const pms = useMemo(() => (data?.prediction_markets ?? []).filter((m) => !pmFilter || m.question.toLowerCase().includes(pmFilter.toLowerCase())), [data, pmFilter])

  const follow = async (id: string, f: boolean) => {
    await api.followMarket(id, f)
    toast(f ? 'Mercado seguido: aparece en la cinta' : 'Dejas de seguir el mercado')
    reload()
  }

  return (
    <div>
      <div className="screen-head">
        <div>
          <h1>Economía / Mercados</h1>
          <div className="sub">Qué descuenta el mercado y por qué canal se transmite un evento. Cada dato lleva fuente y hora.</div>
        </div>
        <div className="tools">
          <button
            type="button"
            className="btn btn-ghost"
            onClick={async () => {
              const r = await api.refreshMarkets()
              toast(r.started ? 'Actualización de mercados lanzada; recarga en un minuto' : (r.reason ?? 'No se pudo lanzar'))
            }}
          >
            Actualizar mercados
          </button>
        </div>
      </div>
      <div className="notice warn" style={{ marginBottom: 12 }}>
        {data?.disclaimer ?? 'Información, no asesoramiento financiero. ATLAS nunca emite órdenes de compra o venta.'}
      </div>
      {loading && !data && <Loading />}
      <ErrorBox error={error} retry={reload} />
      {data && (
        <>
          <div className="row wrap small muted" style={{ marginBottom: 8 }}>
            <span>Última actualización: {data.last_refresh ? `${fmtDateTime(data.last_refresh.finished_at)} (${data.last_refresh.ok ? 'OK' : 'con errores'})` : 'nunca'}</span>
            <span>Cotizaciones: Yahoo Finance (API pública de gráficos). Mercados de predicción: Polymarket (Gamma) y Manifold.</span>
          </div>
          {groups.length === 0 && (
            <EmptyState title="Sin cotizaciones">
              Pulsa «Actualizar mercados» (o `make markets`). Si la máquina no tiene red, la cinta mostrará «sin dato» con el error de cada símbolo.
            </EmptyState>
          )}
          <div className="two-col">
            {groups.map(([g, quotes]) => (
              <section key={g} className="section" style={{ marginTop: 0 }}>
                <h2>{GROUP_LABEL[g] ?? g}</h2>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Activo</th>
                      <th className="num">Precio</th>
                      <th className="num">Var. %</th>
                      <th>30 d</th>
                      <th>Dato</th>
                      <th>Fuente</th>
                    </tr>
                  </thead>
                  <tbody>
                    {quotes.map((q) => (
                      <tr key={q.symbol}>
                        <td>
                          <strong>{q.label}</strong> <span className="muted mono small">{q.symbol}</span>
                        </td>
                        <td className="num">
                          {q.price == null ? <span className="warn">sin dato</span> : fmtPrice(q.price)} {q.currency && q.price != null ? <span className="muted small">{q.currency}</span> : null}
                        </td>
                        <td className="num" style={{ color: (q.change_pct ?? 0) < 0 ? 'var(--c-warn)' : undefined }}>
                          {fmtSignedPct(q.change_pct)}
                        </td>
                        <td>
                          <Sparkline values={q.history.map((h) => h.v)} width={90} height={20} />
                        </td>
                        <td className="mono small">{fmtDateTime(q.observed_at)}</td>
                        <td className="small muted">
                          {q.source}
                          {q.error && <div className="warn">{q.error}</div>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            ))}
          </div>

          <section className="section">
            <div className="section-head">
              <h2>Qué está descontado · mercados de predicción</h2>
              <input type="search" value={pmFilter} onChange={(e) => setPmFilter(e.target.value)} placeholder="Filtrar preguntas…" aria-label="Filtrar mercados" />
            </div>
            {pms.length === 0 && <p className="muted small">Sin mercados de predicción cargados.</p>}
            <table className="table">
              <thead>
                <tr>
                  <th>Pregunta</th>
                  <th className="num">Prob.</th>
                  <th className="num">Volumen</th>
                  <th>Sede</th>
                  <th>Cierre</th>
                  <th>Dato</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pms.map((m) => (
                  <tr key={m.id}>
                    <td>
                      <ExtLink href={m.url}>{m.question}</ExtLink>
                    </td>
                    <td className="num">
                      <span className="bar" style={{ width: 60, display: 'inline-block', verticalAlign: 'middle', marginRight: 6 }}>
                        <i style={{ width: `${(m.probability ?? 0) * 100}%`, background: 'var(--c-accent)' }} />
                      </span>
                      {fmtPct(m.probability)}
                    </td>
                    <td className="num">{fmtVolume(m.volume)}</td>
                    <td>{m.venue}</td>
                    <td className="mono small">{fmtDateTime(m.close_at)}</td>
                    <td className="mono small muted">{fmtDateTime(m.fetched_at)}</td>
                    <td>
                      <button type="button" className={`btn btn-sm ${m.followed ? '' : 'btn-ghost'}`} onClick={() => follow(m.id, !m.followed)}>
                        {m.followed ? 'Siguiendo' : 'Seguir'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="section">
            <div className="section-head">
              <h2>Canales causales</h2>
              <span className="muted small">config/causal_channels.yaml · signo y desfase típico · referencia en el tooltip</span>
            </div>
            {data.channels.length ? <CausalGraph channels={data.channels} /> : <p className="muted">Sin canales configurados.</p>}
            <Card className="flat" style={{ marginTop: 8 }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>De</th>
                    <th>A</th>
                    <th>Signo</th>
                    <th>Desfase</th>
                    <th>Referencia</th>
                  </tr>
                </thead>
                <tbody>
                  {data.channels.map((c, i) => (
                    <tr key={i}>
                      <td>{nodeLabel(c.from)}</td>
                      <td>{nodeLabel(c.to)}</td>
                      <td className="mono">{c.sign}</td>
                      <td className="mono">{c.lag ?? '—'}</td>
                      <td className="muted small">{c.ref ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </section>
        </>
      )}
    </div>
  )
}
