import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { CountryRow } from '../api/types'
import { ErrorBox, Loading } from '../components/ui/basics'
import { DataTable } from '../components/ui/DataTable'
import { useAsync } from '../lib/hooks'
import { blocLabel } from '../lib/labels'
import './screens.css'

const LEVEL_DESC: Record<string, string> = { A: 'Profundidad: ficha completa, primarias vigiladas, PRISMA local, deltas diarios', B: 'Seguimiento: ficha estándar, agencias y 2-4 medios nacionales', C: 'Vigilancia: agencias internacionales; solo alertas de materialidad alta' }

export default function Countries() {
  const nav = useNavigate()
  const [q, setQ] = useState('')
  const { data, error, loading } = useAsync(() => api.countries(), [])
  const rows = useMemo(() => (data?.countries ?? []).filter((c) => !q || c.name.toLowerCase().includes(q.toLowerCase()) || c.iso2.toLowerCase() === q.toLowerCase() || c.name_en.toLowerCase().includes(q.toLowerCase())), [data, q])
  const maxEvents = Math.max(1, ...rows.map((r) => r.events_7d))
  return (
    <div>
      <div className="screen-head">
        <div>
          <h1>Geopolítica / Países</h1>
          <div className="sub">Fichas vivas por país, ordenadas por nivel de atención (config/paises.yaml) y actividad de 7 días.</div>
        </div>
        <div className="tools">
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="País o ISO…" aria-label="Buscar país" />
        </div>
      </div>
      {loading && <Loading />}
      <ErrorBox error={error} />
      {data && (
        <>
          <div className="row wrap small muted" style={{ marginBottom: 8 }}>
            {(['A', 'B', 'C'] as const).map((l) => (
              <span key={l}>
                <span className="chip dark">{l}</span> {LEVEL_DESC[l]}
              </span>
            ))}
          </div>
          {(['A', 'B', 'C'] as const).map((level) => {
            const list = rows.filter((c) => c.level === level)
            if (!list.length) return null
            return (
              <section key={level} className="section" style={{ marginTop: level === 'A' ? 0 : undefined }}>
                <div className="section-head">
                  <h2>Nivel {level}</h2>
                  <span className="muted small">{list.length} países</span>
                </div>
                <DataTable<CountryRow>
                  rows={list}
                  rowKey={(c) => c.iso2}
                  onRow={(c) => nav(`/paises/${c.iso2}`)}
                  initialSort={{ key: 'ev', dir: 'desc' }}
                  columns={[
                    { key: 'iso', label: 'ISO', render: (c) => <span className="mono">{c.iso2}</span>, width: 50 },
                    { key: 'name', label: 'País', render: (c) => <strong>{c.name}</strong>, sort: (c) => c.name },
                    { key: 'bloc', label: 'Bloque', render: (c) => blocLabel(c.bloc), sort: (c) => c.bloc },
                    {
                      key: 'ev',
                      label: 'Eventos 7 d',
                      num: true,
                      sort: (c) => c.events_7d,
                      render: (c) => (
                        <span className="row" style={{ justifyContent: 'flex-end' }}>
                          <span className="bar" style={{ width: 90 }}>
                            <i style={{ width: `${(c.events_7d / maxEvents) * 100}%` }} />
                          </span>
                          <span>{c.events_7d}</span>
                        </span>
                      ),
                    },
                  ]}
                />
              </section>
            )
          })}
        </>
      )}
    </div>
  )
}
