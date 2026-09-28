/* Streaming de agentes: un único lector fetch sobre text/event-stream para GET (/agents/explain, /deepen, /lens,
   /country_changes) y POST (/agents/socratic). El servidor emite eventos `start`, `delta`, `done`, `error` con
   JSON en `data`; el tipo se toma del JSON, no de la línea `event:`.
   No se usa EventSource: su evento nativo `error` colisionaba con el `error` del servidor (los 409/429/5xx se
   tragaban sin mensaje), no expone el cuerpo de la respuesta y reconecta solo (cada reconexión es otra ejecución
   del agente, con su coste). Con fetch el cuerpo del 409 (sin clave) o del 429 (tope de presupuesto) llega
   directamente y un corte antes de `done` se comunica como error explícito. */

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

function messageFromResponse(payload: { detail?: unknown } | null, status: number): string {
  const d = payload?.detail
  if (d && typeof d === 'object' && typeof (d as { message?: unknown }).message === 'string') return (d as { message: string }).message
  if (typeof d === 'string') return d
  return `Error HTTP ${status}`
}

function streamFetch(url: string, init: RequestInit, handlers: StreamHandlers): StreamHandle {
  const ctrl = new AbortController()
  let closed = false
  let terminal = false // se ha visto done | error
  const finish = () => {
    if (closed) return
    closed = true
    handlers.onClose?.()
  }
  const emit = (ev: AgentEvent) => {
    if (closed) return
    if (ev.type === 'done' || ev.type === 'error') terminal = true
    handlers.onEvent(ev)
  }
  void (async () => {
    try {
      const res = await fetch(url, {
        ...init,
        headers: { accept: 'text/event-stream', ...(init.headers as Record<string, string> | undefined) },
        signal: ctrl.signal,
      })
      if (!res.ok || !res.body) {
        const payload = (await res.json().catch(() => null)) as { detail?: unknown } | null
        emit({ type: 'error', message: messageFromResponse(payload, res.status) })
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
        if (ev) emit(ev)
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
      if (!terminal) emit({ type: 'error', message: 'Conexión de streaming interrumpida.' })
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError')) {
        emit({ type: 'error', message: e instanceof Error ? e.message : 'Error de red' })
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

export function streamGet(url: string, handlers: StreamHandlers): StreamHandle {
  return streamFetch(url, { method: 'GET' }, handlers)
}

export function streamPost(url: string, body: unknown, handlers: StreamHandlers): StreamHandle {
  return streamFetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }, handlers)
}
