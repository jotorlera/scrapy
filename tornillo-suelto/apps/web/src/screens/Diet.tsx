import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { DietReport } from '../api/types'
import { Card, EmptyState, ErrorBox, InfoIcon, Loading } from '../components/ui/basics'
import { fmt1, fmtPct } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { axisLabel, axisValueLabel } from '../lib/labels'
import { useStore } from '../state/store'
import './screens.css'

export default function Diet() {
  const [days, setDays] = useState(7)
  const nav = useNavigate()
  const { toast } = useStore()
  const { data, error, loading } = useAsync<DietReport>(() => api.dietReport(days), [days])

  const otherSide = async (topic: string) => {
    // Abre el Prisma del último evento relacionado con el tema (búsqueda por texto en títulos)
    try {
      const r = await api.search(topic, 5)
      const ev = r.events[0]
      if (ev) nav(`/prisma/${ev.id}`)
      else toast('No se encontró un evento reciente sobre ese tema', 'warn')
    } catch {
      toast('No se pudo buscar el evento', 'warn')
    }
  }

  return (
    <div>
      <div className="screen-head">
        <div>
          <h1>Dieta</h1>
          <div className="sub">Anti-burbuja: diversidad de lo que lees en cuatro ejes y puntos ciegos por tema.</div>
        </div>
        <div className="seg">
          {[7, 30, 90].map((d) => (
            <button key={d} type="button" aria-pressed={days === d} onClick={() => setDays(d)}>
              {d} d
            </button>
          ))}
        </div>
      </div>
      <div className="notice" style={{ marginBottom: 12 }}>
        Todo se calcula localmente a partir de tu registro de lectura (aperturas y tiempo). Los datos nunca salen de esta máquina; puedes borrar la tabla `reading_log` cuando quieras.
      </div>
      {loading && !data && <Loading />}
      <ErrorBox error={error} />
      {data && data.n_logs === 0 && <EmptyState title="Sin lecturas registradas en la ventana">Abre eventos y documentos: cada apertura y el tiempo de lectura alimentan el índice. Se necesitan ≥ 5 minutos por tema para detectar un punto ciego.</EmptyState>}
      {data && data.n_logs > 0 && (
        <>
          <div className="row wrap" style={{ marginBottom: 12 }}>
            <div className="stat-tile">
              <div className="v">{fmt1(data.diversity_index * 100)}</div>
              <div className="k">
                índice de diversidad (0-100){' '}
                <InfoIcon label="Cómo se calcula">
                  <h4>Índice de diversidad</h4>
                  <p>Media de la entropía de Shannon normalizada de los cuatro ejes (ideología, bloque, idioma, tipo de fuente) ponderada por segundos de lectura. 100 = reparto uniforme.</p>
                </InfoIcon>
              </div>
            </div>
            <div className="stat-tile">
              <div className="v">{fmt1(data.minutes)}</div>
              <div className="k">minutos leídos</div>
            </div>
            <div className="stat-tile">
              <div className="v">{data.n_logs}</div>
              <div className="k">registros</div>
            </div>
          </div>
          <section className="section" style={{ marginTop: 0 }}>
            <h2>Entropía por eje</h2>
            <div className="hbars" style={{ maxWidth: 560 }}>
              {Object.entries(data.entropy).map(([axis, h]) => (
                <div key={axis} style={{ display: 'contents' }}>
                  <span>{axisLabel(axis)}</span>
                  <span className="bar accent">
                    <i style={{ width: `${h * 100}%` }} />
                  </span>
                  <span className="num">{h.toFixed(2)}</span>
                </div>
              ))}
            </div>
          </section>
          <section className="section">
            <h2>Distribución del tiempo de lectura</h2>
            <div className="biz-cards">
              {Object.entries(data.distribution).map(([axis, dist]) => {
                const total = Object.values(dist).reduce((s, v) => s + v, 0) || 1
                return (
                  <Card key={axis} title={axisLabel(axis)}>
                    <div className="hbars">
                      {Object.entries(dist).map(([k, v]) => (
                        <div key={k} style={{ display: 'contents' }}>
                          <span>{axisValueLabel(axis, k)}</span>
                          <span className="bar">
                            <i style={{ width: `${(v / total) * 100}%` }} />
                          </span>
                          <span className="num">{fmtPct(v / total)}</span>
                        </div>
                      ))}
                    </div>
                  </Card>
                )
              })}
            </div>
          </section>
          <section className="section">
            <h2>Puntos ciegos</h2>
            {data.blind_spots.length === 0 && <p className="muted small">Ningún tema con más del 80 % del tiempo en un solo ecosistema (mínimo 5 minutos por tema).</p>}
            {data.blind_spots.map((b) => (
              <div key={b.topic} className="alert-row">
                <div>
                  <strong>{b.topic}</strong>: {fmtPct(b.share)} de {b.minutes} min desde <span className="chip">{axisValueLabel('ideology', b.ecosystem)}</span>
                </div>
                <button type="button" className="btn btn-sm" onClick={() => otherSide(b.topic)}>
                  Muéstrame el otro lado
                </button>
              </div>
            ))}
          </section>
        </>
      )}
    </div>
  )
}
