import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api/client'
import { startDietSession, type DietLogBody } from './diet'

export interface AsyncState<T> {
  data: T | null
  error: ApiError | Error | null
  loading: boolean
  reload: () => void
}

/** Carga asíncrona con recarga manual. `deps` reinicia la carga. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  const fnRef = useRef(fn)
  fnRef.current = fn
  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)
    fnRef
      .current()
      .then((d) => {
        if (alive) setData(d)
      })
      .catch((e: unknown) => {
        if (alive) setError(e instanceof Error ? e : new Error(String(e)))
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])
  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, loading, reload }
}

/** Envío que sobrevive al cierre de la pestaña: sendBeacon (mismo origen, JSON) y, si no, fetch con keepalive. */
function sendDietLog(body: DietLogBody): void {
  try {
    if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
      const blob = new Blob([JSON.stringify(body)], { type: 'application/json' })
      if (navigator.sendBeacon('/api/diet/log', blob)) return
    }
  } catch {
    /* sin sendBeacon: fetch keepalive */
  }
  void api.dietLog(body, true).catch(() => undefined)
}

/** Registro de dieta: `open` al montar (marcador) y `read` con los segundos realmente visibles al ocultar la
 *  pestaña, al descargar la página o al desmontar (lógica en lib/diet.ts). */
export function useDietLog(ref: { event_id?: string | null; document_id?: string | null }, enabled = true): void {
  const eventId = ref.event_id ?? undefined
  const docId = ref.document_id ?? undefined
  useEffect(() => {
    if (!enabled || (!eventId && !docId)) return
    return startDietSession({ event_id: eventId, document_id: docId }, { send: sendDietLog })
  }, [eventId, docId, enabled])
}

export function useDebounced<T>(value: T, ms = 200): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = window.setTimeout(() => setV(value), ms)
    return () => window.clearTimeout(t)
  }, [value, ms])
  return v
}

export function useInterval(fn: () => void, ms: number | null): void {
  const ref = useRef(fn)
  ref.current = fn
  useEffect(() => {
    if (ms == null) return
    const id = window.setInterval(() => ref.current(), ms)
    return () => window.clearInterval(id)
  }, [ms])
}

export function usePrefersReducedMotion(): boolean {
  const [v, setV] = useState(() => (typeof window !== 'undefined' ? window.matchMedia('(prefers-reduced-motion: reduce)').matches : false))
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const h = () => setV(mq.matches)
    mq.addEventListener('change', h)
    return () => mq.removeEventListener('change', h)
  }, [])
  return v
}

/** Tamaño de un contenedor (ResizeObserver). */
export function useSize<T extends HTMLElement>(): [React.RefObject<T | null>, { width: number; height: number }] {
  const ref = useRef<T | null>(null)
  const [size, setSize] = useState({ width: 0, height: 0 })
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        const { width, height } = e.contentRect
        setSize((s) => (Math.abs(s.width - width) < 1 && Math.abs(s.height - height) < 1 ? s : { width, height }))
      }
    })
    ro.observe(el)
    setSize({ width: el.clientWidth, height: el.clientHeight })
    return () => ro.disconnect()
  }, [])
  return [ref, size]
}

export function useLocalState<T>(key: string, initial: T): [T, (v: T) => void] {
  const [v, setV] = useState<T>(() => {
    try {
      const raw = window.localStorage.getItem(key)
      return raw ? (JSON.parse(raw) as T) : initial
    } catch {
      return initial
    }
  })
  const set = useCallback(
    (nv: T) => {
      setV(nv)
      try {
        window.localStorage.setItem(key, JSON.stringify(nv))
      } catch {
        /* sin almacenamiento */
      }
    },
    [key],
  )
  return [v, set]
}
