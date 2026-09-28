import { useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { EventSummary, WhatIfOutput } from '../api/types'
import { Card, EmptyState, Loading } from '../components/ui/basics'
import { fmtPct } from '../lib/format'
import { useStore } from '../state/store'
import './screens.css'

export default function Simulator() {
  const { agentsEnabled, agents } = useStore()
  const [premise, setPremise] = useState('')
  const [eventId, setEventId] = useState('')
  const [events, setEvents] = useState<EventSummary[]>([])
  const [result, setResult] = useState<WhatIfOutput | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    api.events({ hours: 168, limit: 40 }).then((r) => setEvents(r.events)).catch(() => undefined)
  }, [])
  const run = async () => {
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      setResult(await api.whatIf({ premise: premise.trim(), event_id: eventId || null }))
    } catch (e) {
      setError(e instanceof ApiError ? e.userMessage : String(e))
    } finally {
      setBusy(false)
    }
  }
  const total = result?.scenarios.reduce((s, x) => s + x.probability, 0) ?? 0
  return (
    <div>
      <div className="screen-head">
        <div>
          <h1>Simulador</h1>
          <div className="sub">Modo C · «¿qué pasa si…?»: trayectorias con probabilidad, desencadenantes, señales tempranas y objeción del equipo rojo.</div>
        </div>
        <span className="chip dark">SIMULACIÓN — no es predicción</span>
      </div>
      <div className="two-col narrow-left">
        <Card title="Premisa">
          <div className="col">
            <label className="field">
              Evento de partida (opcional)
              <select value={eventId} onChange={(e) => setEventId(e.target.value)}>
                <option value="">— ninguno —</option>
                {events.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.title_neutral.slice(0, 90)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              ¿Qué pasa si…?
              <textarea rows={5} value={premise} onChange={(e) => setPremise(e.target.value)} placeholder="…el BCE sube 50 pb en la próxima reunión mientras el Brent supera los 110 USD" />
            </label>
            <button type="button" className="btn btn-primary" onClick={run} disabled={!agentsEnabled || busy || premise.trim().length < 10} title={agentsEnabled ? undefined : (agents?.message ?? undefined)}>
              {busy ? 'Simulando…' : 'Generar escenarios'}
            </button>
            {!agentsEnabled && (
              <div className="notice warn">
                {agents?.message ?? 'Agentes desactivados: añade ANTHROPIC_API_KEY en .env y reinicia.'} El simulador genera escenarios con el modelo (superpronosticador + equipo rojo); sin clave no hay nada que mostrar. Los modos A (wargame multiactor) y B (opinión pública) quedan fuera de alcance (docs/spec/08).
              </div>
            )}
            <p className="muted small">Coste máximo por simulación: {String(agents?.limits?.simulation_max_usd_per_run ?? '—')} USD. Las probabilidades suman ≤ 1 y son del modelo, no del sistema de pronóstico.</p>
          </div>
        </Card>
        <div className="col">
          {busy && <Loading text="El superpronosticador está escribiendo escenarios…" />}
          {error && <div className="errorbox">{error}</div>}
          {!result && !busy && !error && <EmptyState title="Sin escenarios">Escribe una premisa contrafactual y pulsa «Generar escenarios». Cada trayectoria trae desencadenantes y señales tempranas para vigilar.</EmptyState>}
          {result && (
            <>
              <div className="notice warn">
                <strong>{result.label}</strong> · probabilidad total de los escenarios: {fmtPct(total)} {result.cost_usd != null ? `· coste ${result.cost_usd.toFixed(4)} USD` : ''}
              </div>
              {result.scenarios.map((s, i) => (
                <Card key={i} title={s.name} extra={<span className="num" style={{ fontSize: 16 }}>{fmtPct(s.probability)}</span>}>
                  <div className="bar accent" style={{ marginBottom: 8 }}>
                    <i style={{ width: `${s.probability * 100}%` }} />
                  </div>
                  <p className="read">{s.description}</p>
                  <div className="two-col small">
                    <div>
                      <div className="label">Desencadenantes</div>
                      <ul style={{ margin: '2px 0 0 16px', padding: 0 }}>
                        {s.triggers.map((t, k) => (
                          <li key={k}>{t}</li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <div className="label">Señales tempranas</div>
                      <ul style={{ margin: '2px 0 0 16px', padding: 0 }}>
                        {s.early_signals.map((t, k) => (
                          <li key={k}>{t}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </Card>
              ))}
              <Card title="Objeción del equipo rojo" surface>
                <p className="read">{result.red_team_objection}</p>
                {result.uncertainties.length > 0 && (
                  <>
                    <div className="label">Incertidumbres</div>
                    <ul style={{ margin: '2px 0 0 16px', padding: 0, fontSize: 'var(--fs-data)' }}>
                      {result.uncertainties.map((u, k) => (
                        <li key={k}>{u}</li>
                      ))}
                    </ul>
                  </>
                )}
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
