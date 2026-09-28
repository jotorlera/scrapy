import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import type { SearchResponse } from '../../api/types'
import { useDebounced } from '../../lib/hooks'
import { useStore } from '../../state/store'
import { Modal } from '../ui/Modal'

interface Item {
  id: string
  kind: string
  text: string
  hint?: string
  run: () => void
}

const norm = (s: string) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

export function CommandPalette() {
  const { paletteOpen, setPaletteOpen, setMode, currentEvent } = useStore()
  const nav = useNavigate()
  const [q, setQ] = useState('')
  const dq = useDebounced(q, 180)
  const [res, setRes] = useState<SearchResponse | null>(null)
  const [sel, setSel] = useState(0)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!paletteOpen) {
      setQ('')
      setRes(null)
      setSel(0)
    }
  }, [paletteOpen])

  useEffect(() => {
    if (!paletteOpen || dq.trim().length < 2) {
      setRes(null)
      return
    }
    let alive = true
    api
      .search(dq.trim())
      .then((r) => alive && setRes(r))
      .catch(() => alive && setRes(null))
    return () => {
      alive = false
    }
  }, [dq, paletteOpen])

  const close = () => setPaletteOpen(false)
  const go = (to: string) => {
    nav(to)
    close()
  }

  const items = useMemo<Item[]>(() => {
    const out: Item[] = []
    const nq = norm(q.trim())
    const actions: Item[] = [
      { id: 'a-radar', kind: 'acción', text: 'Ir a Radar', hint: 'g r', run: () => go('/') },
      { id: 'a-eventos', kind: 'acción', text: 'Ir a Eventos', hint: 'g e', run: () => go('/eventos') },
      { id: 'a-prisma', kind: 'acción', text: 'Ir a Prisma', hint: 'g p', run: () => go('/prisma') },
      { id: 'a-mercados', kind: 'acción', text: 'Ir a Economía / Mercados', hint: 'g m', run: () => go('/mercados') },
      { id: 'a-paises', kind: 'acción', text: 'Ir a Geopolítica / Países', run: () => go('/paises') },
      { id: 'a-agora', kind: 'acción', text: 'Ir a Ágora', hint: 'g a', run: () => go('/agora') },
      { id: 'a-taller', kind: 'acción', text: 'Ir a Taller', hint: 'g t', run: () => go('/taller') },
      { id: 'a-mando', kind: 'acción', text: 'Ir a Mando', hint: 'g c', run: () => go('/mando') },
      { id: 'a-brief', kind: 'acción', text: 'Abrir el Brief', hint: 'g b', run: () => go('/brief') },
      { id: 'a-forecast', kind: 'acción', text: 'Nuevo pronóstico', hint: 'f', run: () => go(`/pronosticos?nuevo=1${currentEvent ? `&evento=${currentEvent.id}` : ''}`) },
      { id: 'a-note', kind: 'acción', text: 'Nueva nota', hint: 'n', run: () => go('/taller?nueva=1') },
      { id: 'a-socratic', kind: 'acción', text: `Tutor socrático${q.trim() ? ` sobre «${q.trim()}»` : ''}`, run: () => go(`/agora?tab=tutor${q.trim() ? `&tema=${encodeURIComponent(q.trim())}` : ''}`) },
      { id: 'a-maquinas', kind: 'acción', text: 'Sala de máquinas', run: () => go('/maquinas') },
      { id: 'a-mode1', kind: 'modo', text: 'Modo ANALISTA', hint: '1', run: () => { setMode('ANALISTA'); go('/') } },
      { id: 'a-mode2', kind: 'modo', text: 'Modo PENSADOR', hint: '2', run: () => { setMode('PENSADOR'); go('/agora') } },
      { id: 'a-mode3', kind: 'modo', text: 'Modo CEO', hint: '3', run: () => { setMode('CEO'); go('/mando') } },
    ]
    if (res) {
      for (const c of res.countries) {
        out.push({ id: `c-${c.iso2}`, kind: 'país', text: `${c.name} (${c.iso2})`, run: () => go(`/paises/${c.iso2}`) })
        out.push({ id: `cq-${c.iso2}`, kind: 'acción', text: `¿Qué ha cambiado en ${c.name} en 7 d?`, run: () => go(`/paises/${c.iso2}?dias=7`) })
      }
      for (const e of res.events) out.push({ id: `e-${e.id}`, kind: 'evento', text: e.title_neutral, hint: e.countries.join(' '), run: () => go(`/eventos/${e.id}`) })
      for (const d of res.documents) out.push({ id: `d-${d.id}`, kind: 'documento', text: d.title ?? d.url, hint: d.source_name, run: () => go(d.event_id ? `/eventos/${d.event_id}` : '/primarias') })
      for (const en of res.entities) out.push({ id: `n-${en.id}`, kind: 'actor', text: en.name, hint: en.kind, run: () => go(`/actores/${en.id}`) })
      for (const n of res.notes) out.push({ id: `note-${n.id}`, kind: 'nota', text: n.title ?? '(sin título)', run: () => go(`/taller?nota=${n.id}`) })
      for (const qq of res.questions) out.push({ id: `q-${qq.id}`, kind: 'pronóstico', text: qq.title, hint: qq.status, run: () => go(`/pronosticos/${qq.id}`) })
      for (const cs of res.cases) out.push({ id: `case-${cs.id}`, kind: 'caso', text: cs.name, hint: cs.category, run: () => go(`/archivo?caso=${cs.id}`) })
    }
    const filteredActions = nq ? actions.filter((a) => norm(a.text).includes(nq) || a.id.includes('socratic')) : actions
    return [...out, ...filteredActions]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [res, q, currentEvent])

  useEffect(() => setSel(0), [items.length])
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(`[data-idx="${sel}"]`)
    el?.scrollIntoView({ block: 'nearest' })
  }, [sel])

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSel((s) => Math.min(items.length - 1, s + 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSel((s) => Math.max(0, s - 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      items[sel]?.run()
    }
  }

  let lastKind = ''
  return (
    <Modal open={paletteOpen} title="Buscar / preguntar" onClose={close}>
      <div className="palette" onKeyDown={onKey}>
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Eventos, documentos, actores, países, notas, preguntas, casos… o una acción" aria-label="Buscar" autoFocus />
        <div className="results" role="listbox" ref={listRef}>
          {items.map((it, i) => {
            const showTitle = it.kind !== lastKind
            lastKind = it.kind
            return (
              <div key={it.id}>
                {showTitle && <div className="label group-title">{it.kind}</div>}
                <div role="option" aria-selected={i === sel} data-idx={i} className="item" onMouseEnter={() => setSel(i)} onClick={it.run}>
                  <span className="kind">{it.kind}</span>
                  <span className="txt">{it.text}</span>
                  {it.hint && <span className="muted small mono">{it.hint}</span>}
                </div>
              </div>
            )
          })}
          {q.trim().length >= 2 && res && items.every((i) => i.kind === 'acción' || i.kind === 'modo') && <div className="item muted">Sin resultados en el archivo para «{q}».</div>}
        </div>
        <div className="foot">
          <span>↑↓ moverse</span>
          <span>Enter abrir</span>
          <span>Esc cerrar</span>
          <span className="grow" />
          <span>Busca en GET /api/search</span>
        </div>
      </div>
    </Modal>
  )
}
