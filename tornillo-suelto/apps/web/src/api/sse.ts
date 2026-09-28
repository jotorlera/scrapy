/* Streaming de agentes.
   - `streamGet`: EventSource sobre los GET (/agents/explain, /deepen, /lens, /country_changes).
   - `streamPost`: fetch con lector de stream para POST /agents/socratic.
   El servidor emite eventos `start`, `delta`, `done`, `error` con JSON en `data`. Sin clave responde 409 con
   el estado del presupuesto; EventSource no expone el cuerpo, así que en el error se consulta la URL con fetch
   para recuperar el mensaje. */

import type { AgentEvent } from './types'

export interface StreamHandlers {
  onEvent: (ev: AgentEvent) => void
  onClose?: () => void
}

export interface StreamHandle {
  close: () => void
}

function parseData(raw: string): AgentEvent | null {
  try {
    return JSON.parse(raw) as AgentEvent
  } catch {
    return null
  }
}

async function errorMessageFor(url: string): Promise<string> {
  try {
    const res = await fetch(url, { headers: { accept: 'application/json' } })
    if (res.ok) return 'Conexión de streaming interrumpida.'
    const body = (await res.json().catch(() => null)) as { detail?: unknown } | null
    const d = body?.detail
    if (d && typeof d === 'object' && typeof (d as { message?: unknown }).message === 'string') return (d as { message: string }).message
    if (typeof d === 'string') return d
    return `Error HTTP ${res.status}`
  } catch (e) {
    return e instanceof Error ? e.message : 'Error de red'
  }
}

export function streamGet(url: string, handlers: StreamHandlers): StreamHandle {
  const es = new EventSource(url)
  let gotSomething = false
  let closed = false
  const finish = () => {
    if (closed) return
    closed = true
    es.close()
    handlers.onClose?.()
  }
  for (const name of ['start', 'delta', 'done', 'error'] as const) {
    es.addEventListener(name, (e) => {
      gotSomething = true
      const ev = parseData((e as MessageEvent).data as string)
      if (ev) handlers.onEvent(ev)
      if (name === 'done' || name === 'error') finish()
    })
  }
  es.onmessage = (e) => {
    const ev = parseData(e.data as string)
    if (ev) handlers.onEvent(ev)
  }
  es.onerror = () => {
    if (closed) return
    if (!gotSomething) {
      void errorMessageFor(url).then((message) => {
        handlers.onEvent({ type: 'error', message })
        finish()
      })
    } else {
      finish()
    }
  }
  return { close: finish }
}

export function streamPost(url: string, body: unknown, handlers: StreamHandlers): StreamHandle {
  const ctrl = new AbortController()
  let closed = false
  const finish = () => {
    if (closed) return
    closed = true
    handlers.onClose?.()
  }
  void (async () => {
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
        body: JSON.stringify(body),
        signal: ctrl.signal,
      })
      if (!res.ok || !res.body) {
        const payload = (await res.json().catch(() => null)) as { detail?: unknown } | null
        const d = payload?.detail
        const message =
          d && typeof d === 'object' && typeof (d as { message?: unknown }).message === 'string'
            ? (d as { message: string }).message
            : typeof d === 'string'
              ? d
              : `Error HTTP ${res.status}`
        handlers.onEvent({ type: 'error', message })
        finish()
        return
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      const dispatch = (frame: string) => {
        let data = ''
        for (const line of frame.split('\n')) {
          if (line.startsWith('data:')) data += line.slice(5).trim()
        }
        if (!data) return
        const ev = parseData(data)
        if (ev) handlers.onEvent(ev)
      }
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let idx: number
        while ((idx = buffer.indexOf('\n\n')) >= 0) {
          const frame = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          dispatch(frame.replace(/\r/g, ''))
        }
      }
      if (buffer.trim()) dispatch(buffer)
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError')) {
        handlers.onEvent({ type: 'error', message: e instanceof Error ? e.message : 'Error de red' })
      }
    } finally {
      finish()
    }
  })()
  return {
    close: () => {
      ctrl.abort()
      finish()
    },
  }
}
