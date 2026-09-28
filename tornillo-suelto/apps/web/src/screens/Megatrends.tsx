import { useMemo } from 'react'
import { api } from '../api/client'
import type { EventSummary } from '../api/types'
import { Card, EmptyState, ErrorBox, Loading } from '../components/ui/basics'
import { EventCard } from '../components/ui/EventCard'
import { fmtDate } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { useStore } from '../state/store'
import './screens.css'

const PANELS = [
  { name: 'Demografía', source: 'UN World Population Prospects', what: 'población, envejecimiento, migración neta' },
  { name: 'Energía y emisiones', source: 'AIE · Ember · OWID', what: 'mix eléctrico, demanda, CO₂' },
  { name: 'Deuda', source: 'FMI (WEO, Fiscal Monitor)', what: 'deuda/PIB, servicio de la deuda' },
  { name: 'Agua y alimentos', source: 'FAO', what: 'índice de precios, estrés hídrico' },
  { name: 'Salud y envejecimiento', source: 'OMS · IHME/GBD', what: 'esperanza de vida, carga de enfermedad' },
  { name: 'Tecnología e IA', source: 'indicadores de inversión y cómputo', what: 'capex, capacidad de cómputo' },
  { name: 'Urbanización', source: 'UN DESA', what: 'población urbana, megaciudades' },
]

const THEMES: Array<{ key: string; label: string; match: RegExp }> = [
  { key: 'clima', label: 'Clima', match: /clima|climate|emisi|carbon/i },
  { key: 'energia', label: 'Energía', match: /energ|petr|gas|nuclear|renovable/i },
  { key: 'sanidad', label: 'Sanidad', match: /sanidad|salud|health|pandem|vacun/i },
  { key: 'ia', label: 'IA', match: /\bIA\b|inteligencia artificial|\bAI\b|chips|semicond/i },
  { key: 'deuda', label: 'Deuda', match: /deuda|debt|déficit|deficit|fiscal/i },
]

export default function Megatrends() {
  const { setCurrentEvent } = useStore()
  const { data, error, loading } = useAsync<{ events: EventSummary[] }>(() => api.events({ hours: 720, limit: 300 }), [])
  const signals = useMemo(() => {
    const out = new Map<string, EventSummary[]>()
    for (const t of THEMES) out.set(t.key, [])
    for (const e of data?.events ?? []) {
      for (const t of THEMES) {
        if (e.topics.some((tp) => t.match.test(tp)) || t.match.test(e.title_neutral)) out.get(t.key)!.push(e)
      }
    }
    return out
  }, [data])
  return (
    <div>
      <div className="screen-head">
        <div>
          <h1>Megatendencias</h1>
          <div className="sub">Fuerzas lentas que dominan el largo plazo. Estado honesto: los paneles de series largas todavía no tienen conector.</div>
        </div>
      </div>
      <EmptyState title="Paneles de series largas: pendientes de conector">
        Los siete paneles previstos requieren conectores de datos (UN WPP, AIE, FMI, FAO, OMS…) que aún no están activados en este motor. Cuando existan, cada panel mostrará fuente y fecha de cada serie. Mientras tanto, abajo se listan los eventos recientes etiquetados con temas estructurales como <strong>señales de megatendencia</strong>.
      </EmptyState>
      <div className="biz-cards" style={{ margin: '12px 0' }}>
        {PANELS.map((p) => (
          <Card key={p.name} title={p.name} extra={<span className="chip provenance">sin conector</span>}>
            <div className="small muted">{p.source}</div>
            <div className="small">{p.what}</div>
          </Card>
        ))}
      </div>
      <section className="section">
        <div className="section-head">
          <h2>Señales de megatendencia (30 d)</h2>
          <span className="muted small">eventos cuyos temas o títulos mencionan Clima, Energía, Sanidad, IA o Deuda</span>
        </div>
        {loading && <Loading />}
        <ErrorBox error={error} />
        <div className="two-col">
          {THEMES.map((t) => {
            const list = (signals.get(t.key) ?? []).slice(0, 8)
            return (
              <Card key={t.key} title={t.label} extra={<span className="muted small">{signals.get(t.key)?.length ?? 0} eventos</span>}>
                {list.length === 0 && <div className="muted small">Sin señales en la ventana.</div>}
                {list.map((e) => (
                  <div key={e.id} className="row" style={{ alignItems: 'flex-start', gap: 8 }}>
                    <span className="mono muted small" style={{ minWidth: 76, paddingTop: 10 }}>
                      {fmtDate(e.first_seen_at)}
                    </span>
                    <div className="grow">
                      <EventCard event={e} onSelect={setCurrentEvent} />
                    </div>
                  </div>
                ))}
              </Card>
            )
          })}
        </div>
      </section>
    </div>
  )
}
