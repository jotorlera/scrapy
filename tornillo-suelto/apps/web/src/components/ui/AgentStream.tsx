import { useCallback, useEffect, useRef, useState } from 'react'
import { streamGet, streamPost, type StreamHandle } from '../../api/sse'
import { useStore } from '../../state/store'
import { Markdown } from './Markdown'

export interface AgentStreamProps {
  title: string
  url: string
  method?: 'GET' | 'POST'
  body?: unknown
  /** Cambiar la clave reinicia el streaming. */
  runKey: string
  autoStart?: boolean
  onDone?: (text: string) => void
}

/** Salida de un agente en streaming (eventos start/delta/done/error). */
export function AgentStream({ title, url, method = 'GET', body, runKey, autoStart = true, onDone }: AgentStreamProps) {
  const { agentsEnabled, agents } = useStore()
  const [text, setText] = useState('')
  const [model, setModel] = useState<string | null>(null)
  const [state, setState] = useState<'idle' | 'running' | 'done' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)
  const handle = useRef<StreamHandle | null>(null)

  const start = useCallback(() => {
    handle.current?.close()
    setText('')
    setModel(null)
    setError(null)
    setState('running')
    const handlers = {
      onEvent: (ev: { type: string; [k: string]: unknown }) => {
        if (ev.type === 'start') setModel((ev.model as string | null) ?? null)
        else if (ev.type === 'delta') setText((t) => t + (ev.text as string))
        else if (ev.type === 'done') {
          setState('done')
          const full = (ev.text as string) || ''
          if (full) setText(full)
          onDone?.(full)
        } else if (ev.type === 'error') {
          setError(ev.message as string)
          setState('error')
        }
      },
      onClose: () => setState((s) => (s === 'running' ? 'done' : s)),
    }
    handle.current = method === 'POST' ? streamPost(url, body, handlers) : streamGet(url, handlers)
  }, [url, method, body, onDone])

  useEffect(() => {
    if (autoStart && agentsEnabled) start()
    return () => handle.current?.close()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runKey, agentsEnabled])

  return (
    <div className="agent-stream">
      <div className="head">
        <div>
          <strong>{title}</strong>
          <div className="small muted">
            {model ? `modelo ${model}` : agents?.models?.analysis ? `modelo previsto ${agents.models.analysis}` : 'agente'} · salida de modelo, no verificada
          </div>
        </div>
        <div className="row">
          {state === 'running' && (
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => handle.current?.close()}>
              Detener
            </button>
          )}
          {(state === 'done' || state === 'error') && (
            <button type="button" className="btn btn-sm btn-ghost" onClick={start} disabled={!agentsEnabled}>
              Repetir
            </button>
          )}
        </div>
      </div>
      {!agentsEnabled && <div className="notice warn">{agents?.message ?? 'Agentes desactivados: añade ANTHROPIC_API_KEY en .env y reinicia.'}</div>}
      {error && <div className="errorbox">{error}</div>}
      <div className={`body ${state === 'running' ? 'cursor' : ''}`}>{text ? <Markdown text={text} /> : state === 'running' ? <span className="muted">Esperando al modelo…</span> : null}</div>
    </div>
  )
}
