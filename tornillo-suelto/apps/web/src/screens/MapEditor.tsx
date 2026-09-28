import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { ArgumentEdge, ArgumentNode, EdgeRel, MapDetail, NodeKind } from '../api/types'
import { Card, ErrorBox, Loading } from '../components/ui/basics'
import { useAsync } from '../lib/hooks'
import { EDGE_REL_LABEL, NODE_KIND_LABEL } from '../lib/labels'
import { useStore } from '../state/store'
import './screens.css'

const NODE_W = 190
const NODE_H = 64
const KINDS = Object.keys(NODE_KIND_LABEL) as NodeKind[]
const RELS = Object.keys(EDGE_REL_LABEL) as EdgeRel[]

function wrap(text: string, max = 32, lines = 3): string[] {
  const words = text.split(/\s+/)
  const out: string[] = []
  let cur = ''
  for (const w of words) {
    if ((cur + ' ' + w).trim().length > max) {
      out.push(cur.trim())
      cur = w
      if (out.length === lines) break
    } else cur = `${cur} ${w}`
  }
  if (out.length < lines && cur.trim()) out.push(cur.trim())
  if (out.length === lines && words.join(' ').length > out.join(' ').length) out[lines - 1] = `${out[lines - 1].slice(0, max - 1)}…`
  return out
}

/** Forma según el tipo: tesis rectángulo relleno, premisa rectángulo, objeción trazo discontinuo, réplica esquina cortada, evidencia doble borde, autor/obra fondo gris. */
function Shape({ kind }: { kind: NodeKind }) {
  if (kind === 'reply') return <polygon className="shape" points={`0,0 ${NODE_W - 12},0 ${NODE_W},12 ${NODE_W},${NODE_H} 0,${NODE_H}`} />
  if (kind === 'evidence')
    return (
      <>
        <rect className="shape" width={NODE_W} height={NODE_H} />
        <rect className="shape" x={3} y={3} width={NODE_W - 6} height={NODE_H - 6} fill="none" />
      </>
    )
  if (kind === 'author') return <polygon className="shape" points={`12,0 ${NODE_W - 12},0 ${NODE_W},${NODE_H / 2} ${NODE_W - 12},${NODE_H} 12,${NODE_H} 0,${NODE_H / 2}`} />
  return <rect className="shape" width={NODE_W} height={NODE_H} />
}

export default function MapEditor() {
  const { id = '' } = useParams()
  const { toast } = useStore()
  const { data, error, loading, reload } = useAsync<MapDetail>(() => api.map(id), [id])
  const [nodes, setNodes] = useState<ArgumentNode[]>([])
  const [selNode, setSelNode] = useState<string | null>(null)
  const [selEdge, setSelEdge] = useState<string | null>(null)
  const [linkFrom, setLinkFrom] = useState<string | null>(null)
  const [rel, setRel] = useState<EdgeRel>('supports')
  const [form, setForm] = useState<{ kind: NodeKind; text: string; author: string; work: string }>({ kind: 'premise', text: '', author: '', work: '' })
  const [view, setView] = useState({ x: 0, y: 0, k: 1 })
  const svgRef = useRef<SVGSVGElement>(null)
  const drag = useRef<{ id: string; dx: number; dy: number; moved: boolean } | null>(null)
  const pan = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null)

  useEffect(() => {
    if (!data) return
    // Colocar los nodos sin coordenadas en una rejilla
    let i = 0
    setNodes(
      data.nodes.map((n) => {
        if (n.x == null || n.y == null) {
          const col = i % 4
          const row = Math.floor(i / 4)
          i++
          return { ...n, x: 40 + col * (NODE_W + 40), y: 40 + row * (NODE_H + 60) }
        }
        return n
      }),
    )
  }, [data])

  const edges = data?.edges ?? []
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes])

  const toSvg = useCallback(
    (clientX: number, clientY: number) => {
      const svg = svgRef.current
      if (!svg) return { x: 0, y: 0 }
      const r = svg.getBoundingClientRect()
      return { x: (clientX - r.left - view.x) / view.k, y: (clientY - r.top - view.y) / view.k }
    },
    [view],
  )

  const onNodeDown = (e: React.MouseEvent, n: ArgumentNode) => {
    e.stopPropagation()
    const p = toSvg(e.clientX, e.clientY)
    drag.current = { id: n.id, dx: p.x - (n.x ?? 0), dy: p.y - (n.y ?? 0), moved: false }
  }
  const onMove = (e: React.MouseEvent) => {
    if (drag.current) {
      const p = toSvg(e.clientX, e.clientY)
      const d = drag.current
      d.moved = true
      setNodes((ns) => ns.map((n) => (n.id === d.id ? { ...n, x: p.x - d.dx, y: p.y - d.dy } : n)))
    } else if (pan.current) {
      const p = pan.current
      setView((v) => ({ ...v, x: p.vx + (e.clientX - p.x), y: p.vy + (e.clientY - p.y) }))
    }
  }
  const onUp = async () => {
    if (drag.current) {
      const d = drag.current
      drag.current = null
      const n = byId.get(d.id)
      if (d.moved && n) {
        await api.updateNode(n.id, { x: Math.round(n.x ?? 0), y: Math.round(n.y ?? 0) }).catch(() => toast('No se pudo guardar la posición', 'warn'))
      } else if (!d.moved) {
        if (linkFrom && linkFrom !== d.id) {
          await api.addEdge(id, { src: linkFrom, dst: d.id, rel })
          setLinkFrom(null)
          reload()
          toast(`Arista «${EDGE_REL_LABEL[rel]}» creada`)
        } else {
          setSelNode(d.id)
          setSelEdge(null)
        }
      }
    }
    pan.current = null
  }
  const onBgDown = (e: React.MouseEvent) => {
    pan.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y }
    setSelNode(null)
    setSelEdge(null)
  }
  const onWheel = (e: React.WheelEvent) => {
    const k = Math.min(2.5, Math.max(0.4, view.k * (e.deltaY < 0 ? 1.1 : 0.9)))
    setView((v) => ({ ...v, k }))
  }

  const addNode = async () => {
    if (!form.text.trim()) return
    const p = { x: 60 - view.x / view.k + Math.random() * 80, y: 60 - view.y / view.k + Math.random() * 80 }
    await api.addNode(id, { kind: form.kind, text: form.text.trim(), author: form.author.trim() || undefined, work: form.work.trim() || undefined, x: Math.round(p.x), y: Math.round(p.y) })
    setForm((f) => ({ ...f, text: '', author: '', work: '' }))
    reload()
    toast('Nodo añadido (fechado: muestra la evolución de tu pensamiento)')
  }
  const deleteSelected = async () => {
    if (selNode) {
      if (!window.confirm('¿Borrar el nodo y sus aristas?')) return
      await api.deleteNode(selNode)
      setSelNode(null)
    } else if (selEdge) {
      await api.deleteEdge(selEdge)
      setSelEdge(null)
    }
    reload()
  }
  const saveText = async (n: ArgumentNode, text: string) => {
    await api.updateNode(n.id, { text })
    setNodes((ns) => ns.map((x) => (x.id === n.id ? { ...x, text } : x)))
  }

  if (loading && !data) return <Loading text="Cargando mapa…" />
  if (error) return <ErrorBox error={error} retry={reload} />
  if (!data) return null
  const sel = selNode ? byId.get(selNode) : null

  const edgePath = (e: ArgumentEdge) => {
    const a = byId.get(e.src)
    const b = byId.get(e.dst)
    if (!a || !b) return null
    const ax = (a.x ?? 0) + NODE_W / 2
    const ay = (a.y ?? 0) + NODE_H / 2
    const bx = (b.x ?? 0) + NODE_W / 2
    const by = (b.y ?? 0) + NODE_H / 2
    // recortar en el borde del nodo destino
    const dx = bx - ax
    const dy = by - ay
    const len = Math.hypot(dx, dy) || 1
    const tx = bx - (dx / len) * (NODE_H / 2 + 8)
    const ty = by - (dy / len) * (NODE_H / 2 + 8)
    const sx = ax + (dx / len) * (NODE_H / 2)
    const sy = ay + (dy / len) * (NODE_H / 2)
    return `M${sx},${sy} L${tx},${ty}`
  }

  return (
    <div>
      <div className="screen-head">
        <div>
          <div className="row small">
            <Link to="/agora">← Ágora</Link>
            {data.map.topic && <span className="chip">{data.map.topic}</span>}
          </div>
          <h1>{data.map.title}</h1>
          <div className="sub">
            {nodes.length} nodos · {edges.length} aristas · arrastra para mover (se guarda), rueda para zoom, fondo para desplazar.
          </div>
        </div>
        <div className="tools">
          <span className="label">Enlazar</span>
          <select value={rel} onChange={(e) => setRel(e.target.value as EdgeRel)} aria-label="Relación">
            {RELS.map((r) => (
              <option key={r} value={r}>
                {EDGE_REL_LABEL[r]}
              </option>
            ))}
          </select>
          <button type="button" className={`btn btn-sm ${linkFrom ? '' : 'btn-ghost'}`} disabled={!selNode && !linkFrom} onClick={() => setLinkFrom(linkFrom ? null : selNode)}>
            {linkFrom ? 'Elige el destino…' : 'Desde el nodo seleccionado'}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={deleteSelected} disabled={!selNode && !selEdge}>
            Borrar selección
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setView({ x: 0, y: 0, k: 1 })}>
            Reencuadrar
          </button>
        </div>
      </div>
      <div className="map-editor">
        <div className="map-canvas">
          <svg ref={svgRef} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp} onMouseDown={onBgDown} onWheel={onWheel} role="application" aria-label="Lienzo del mapa argumental">
            <defs>
              <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill="var(--c-ink)" />
              </marker>
              <marker id="arr-att" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill="var(--c-warn)" />
              </marker>
              <marker id="arr-mut" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill="var(--c-muted)" />
              </marker>
            </defs>
            <g transform={`translate(${view.x},${view.y}) scale(${view.k})`}>
              {edges.map((e) => {
                const d = edgePath(e)
                if (!d) return null
                return (
                  <g key={e.id}>
                    <path className={`arg-edge ${e.rel} ${selEdge === e.id ? 'selected' : ''}`} d={d} markerEnd={e.rel === 'attacks' ? 'url(#arr-att)' : e.rel === 'instantiates' ? 'url(#arr-mut)' : 'url(#arr)'} />
                    <path
                      className="arg-edge-hit"
                      d={d}
                      onMouseDown={(ev) => {
                        ev.stopPropagation()
                        setSelEdge(e.id)
                        setSelNode(null)
                      }}
                    >
                      <title>{EDGE_REL_LABEL[e.rel]}</title>
                    </path>
                  </g>
                )
              })}
              {nodes.map((n) => (
                <g key={n.id} className={`arg-node ${selNode === n.id ? 'selected' : ''} ${drag.current?.id === n.id ? 'dragging' : ''}`} data-kind={n.kind} transform={`translate(${n.x ?? 0},${n.y ?? 0})`} onMouseDown={(e) => onNodeDown(e, n)} tabIndex={0} role="button" aria-label={`${NODE_KIND_LABEL[n.kind]}: ${n.text}`} onKeyDown={(e) => e.key === 'Enter' && setSelNode(n.id)}>
                  <Shape kind={n.kind} />
                  <text className="kind" x={8} y={13}>
                    {(() => {
                      const k = `${NODE_KIND_LABEL[n.kind].toUpperCase()}${n.is_user ? ' · tuyo' : ''}${n.author ? ` · ${n.author}` : ''}`
                      return k.length > 34 ? `${k.slice(0, 33)}…` : k
                    })()}
                  </text>
                  {wrap(n.text).map((line, i) => (
                    <text key={i} x={8} y={28 + i * 13}>
                      {line}
                    </text>
                  ))}
                </g>
              ))}
            </g>
          </svg>
        </div>
        <aside className="map-side">
          <Card title="Análisis">
            <div className="col small">
              <div>
                <div className="label">Premisas o tesis sin apoyo ({data.analysis.unsupported.length})</div>
                {data.analysis.unsupported.length === 0 && <span className="muted">Ninguna.</span>}
                {data.analysis.unsupported.map((u) => (
                  <button key={u.id} type="button" className="btn-link" style={{ display: 'block', textAlign: 'left' }} onClick={() => setSelNode(u.id)}>
                    · {u.text}
                  </button>
                ))}
              </div>
              <div>
                <div className="label">Objeciones sin respuesta ({data.analysis.unanswered_objections.length})</div>
                {data.analysis.unanswered_objections.length === 0 && <span className="muted">Ninguna.</span>}
                {data.analysis.unanswered_objections.map((u) => (
                  <button key={u.id} type="button" className="btn-link" style={{ display: 'block', textAlign: 'left' }} onClick={() => setSelNode(u.id)}>
                    · {u.text}
                  </button>
                ))}
              </div>
              <div>
                <div className="label">Ciclos de apoyo (circularidad) ({data.analysis.support_cycles.length})</div>
                {data.analysis.support_cycles.length === 0 && <span className="muted">Ninguno.</span>}
                {data.analysis.support_cycles.map((c, i) => (
                  <div key={i} className="warn">
                    {c.map((nid) => byId.get(nid)?.text.slice(0, 30) ?? nid).join(' → ')}
                  </div>
                ))}
              </div>
            </div>
          </Card>
          {sel && (
            <Card title={`${NODE_KIND_LABEL[sel.kind]}${sel.is_user ? ' · tuyo' : ''}`} extra={<span className="muted small mono">{sel.created_at.slice(0, 10)}</span>}>
              <textarea rows={4} defaultValue={sel.text} key={sel.id} onBlur={(e) => e.target.value !== sel.text && saveText(sel, e.target.value)} aria-label="Texto del nodo" style={{ width: '100%' }} />
              {(sel.author || sel.work) && (
                <div className="small muted" style={{ marginTop: 4 }}>
                  {sel.author} {sel.work ? `· ${sel.work}` : ''}
                </div>
              )}
              <div className="small muted" style={{ marginTop: 4 }}>
                Entrantes: {edges.filter((e) => e.dst === sel.id).map((e) => `${EDGE_REL_LABEL[e.rel]} ← ${byId.get(e.src)?.text.slice(0, 24) ?? '?'}`).join('; ') || '—'}
              </div>
            </Card>
          )}
          <Card title="Añadir nodo">
            <div className="col">
              <label className="field">
                Tipo
                <select value={form.kind} onChange={(e) => setForm((f) => ({ ...f, kind: e.target.value as NodeKind }))}>
                  {KINDS.map((k) => (
                    <option key={k} value={k}>
                      {NODE_KIND_LABEL[k]}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                Texto
                <textarea rows={3} value={form.text} onChange={(e) => setForm((f) => ({ ...f, text: e.target.value }))} />
              </label>
              <div className="two-col" style={{ gap: 6 }}>
                <label className="field">
                  Autor
                  <input type="text" value={form.author} onChange={(e) => setForm((f) => ({ ...f, author: e.target.value }))} />
                </label>
                <label className="field">
                  Obra
                  <input type="text" value={form.work} onChange={(e) => setForm((f) => ({ ...f, work: e.target.value }))} />
                </label>
              </div>
              <button type="button" className="btn btn-primary" onClick={addNode} disabled={!form.text.trim()}>
                Añadir
              </button>
              <p className="muted small">Para una arista: selecciona el origen, pulsa «Desde el nodo seleccionado», elige la relación y haz clic en el destino.</p>
            </div>
          </Card>
        </aside>
      </div>
    </div>
  )
}
