import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Mode } from '../api/types'

const GOTO: Record<string, string> = {
  r: '/',
  e: '/eventos',
  p: '/prisma',
  i: '/primarias',
  m: '/mercados',
  g: '/paises',
  o: '/actores',
  a: '/agora',
  h: '/archivo',
  n: '/megatendencias',
  t: '/taller',
  f: '/pronosticos',
  c: '/mando',
  s: '/simulador',
  b: '/brief',
  d: '/dieta',
  x: '/maquinas',
}

function isTyping(el: Element | null): boolean {
  if (!el) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (el as HTMLElement).isContentEditable
}

function navItems(): HTMLElement[] {
  const main = document.querySelector('main')
  if (!main) return []
  return Array.from(main.querySelectorAll<HTMLElement>('[data-nav-item]')).filter((el) => el.offsetParent !== null)
}

/** Atajos globales estilo gmail: `g x`, `j/k`, `o`, `n`, `f`, `?`, `1/2/3`, ⌘K, `[`. */
export function useGlobalShortcuts(h: { openPalette: () => void; openHelp: () => void; setMode: (m: Mode) => void; togglePanel: () => void; anyModalOpen: () => boolean }) {
  const nav = useNavigate()
  const pending = useRef<{ key: string; t: number } | null>(null)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey
      if (meta && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        h.openPalette()
        return
      }
      if (meta || e.altKey) return
      if (isTyping(document.activeElement)) return
      if (h.anyModalOpen()) return
      const k = e.key
      const now = Date.now()
      if (pending.current && now - pending.current.t < 900) {
        const first = pending.current.key
        pending.current = null
        if (first === 'g' && GOTO[k]) {
          e.preventDefault()
          nav(GOTO[k])
          return
        }
      }
      if (k === 'g') {
        pending.current = { key: 'g', t: now }
        return
      }
      if (k === '?') {
        e.preventDefault()
        h.openHelp()
        return
      }
      if (k === '1' || k === '2' || k === '3') {
        const modes: Mode[] = ['ANALISTA', 'PENSADOR', 'CEO']
        const m = modes[Number(k) - 1]
        h.setMode(m)
        nav(m === 'ANALISTA' ? '/' : m === 'PENSADOR' ? '/agora' : '/mando')
        return
      }
      if (k === 'j' || k === 'k') {
        const items = navItems()
        if (!items.length) return
        e.preventDefault()
        const idx = items.indexOf(document.activeElement as HTMLElement)
        const next = k === 'j' ? Math.min(items.length - 1, idx + 1) : Math.max(0, idx < 0 ? 0 : idx - 1)
        items[next]?.focus()
        items[next]?.scrollIntoView({ block: 'nearest' })
        return
      }
      if (k === 'o') {
        const el = document.activeElement as HTMLElement | null
        if (el && el.hasAttribute('data-nav-item')) {
          e.preventDefault()
          el.click()
        }
        return
      }
      if (k === 'n') {
        e.preventDefault()
        nav('/taller?nueva=1')
        return
      }
      if (k === 'f') {
        e.preventDefault()
        nav('/pronosticos?nuevo=1')
        return
      }
      if (k === '[') {
        e.preventDefault()
        h.togglePanel()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [h, nav])
}
