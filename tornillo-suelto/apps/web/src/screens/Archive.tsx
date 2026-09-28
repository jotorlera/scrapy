import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { CaseCompare, HistoricalCase } from '../api/types'
import { Card, CountryChips, EmptyState, ErrorBox, Loading } from '../components/ui/basics'
import { DataTable } from '../components/ui/DataTable'
import { useAsync, useDebounced } from '../lib/hooks'
import { caseCategoryLabel } from '../lib/labels'
import './screens.css'

function CompareTable({ compare }: { compare: CaseCompare }) {
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Variable</th>
          {compare.outcomes.map((o) => (
            <th key={o.name}>{o.name}</th>
          ))}
          <th>Coinciden</th>
        </tr>
      </thead>
      <tbody>
        {compare.variables.map((v) => (
          <tr key={v.variable}>
            <td>{v.variable}</td>
            {v.values.map((x, i) => (
              <td key={i} className="mono">
                {x == null ? '—' : String(x)}
              </td>
            ))}
            <td>{v.agree ? <span style={{ color: 'var(--c-confirmed)' }}>sí</span> : <span className="warn">no</span>}</td>
          </tr>
        ))}
        <tr>
          <td>
            <strong>Desenlace</strong>
          </td>
          {compare.outcomes.map((o) => (
            <td key={o.name} className="small">
              {o.outcome} {o.duration_months != null ? <span className="muted">({o.duration_months} meses)</span> : null}
            </td>
          ))}
          <td />
        </tr>
      </tbody>
    </table>
  )
}

function CaseSheet({ c }: { c: HistoricalCase }) {
  return (
    <Card title={c.name} extra={<span className="chip">{caseCategoryLabel(c.category)}</span>}>
      <div className="row wrap small muted" style={{ marginBottom: 6 }}>
        <span className="mono">
          {c.start_date} → {c.end_date ?? 'en curso'}
        </span>
        {c.duration_months != null && <span>{c.duration_months} meses</span>}
        <CountryChips countries={c.countries} max={8} />
      </div>
      {c.summary && <p className="read">{c.summary}</p>}
      <div className="label">Desenlace</div>
      <p>{c.outcome}</p>
      <div className="label">Variables codificadas</div>
      <dl className="kv" style={{ marginBottom: 8 }}>
        {Object.entries(c.variables).map(([k, v]) => (
          <div key={k} style={{ display: 'contents' }}>
            <dt>{k}</dt>
            <dd className="mono">{String(v)}</dd>
          </div>
        ))}
      </dl>
      <div className="label">Fuentes</div>
      <ul style={{ margin: '2px 0 0 16px', padding: 0, fontSize: 'var(--fs-data)' }}>
        {c.sources.map((s, i) => (
          <li key={i} className={s.toLowerCase().includes('semilla') ? 'warn' : undefined}>
            {s}
          </li>
        ))}
      </ul>
    </Card>
  )
}

export default function Archive() {
  const [params, setParams] = useSearchParams()
  const [q, setQ] = useState('')
  const [cat, setCat] = useState('')
  const dq = useDebounced(q, 250)
  const { data, error, loading } = useAsync(() => api.cases({ q: dq || undefined, category: cat || undefined }), [dq, cat])
  const selectedId = params.get('caso')
  const selected = useMemo(() => data?.cases.find((c) => c.id === selectedId) ?? null, [data, selectedId])

  const [aq, setAq] = useState('')
  const [analogQuery, setAnalogQuery] = useState('')
  const analogs = useAsync(() => (analogQuery ? api.analogs({ q: analogQuery, n: 4 }) : Promise.resolve(null)), [analogQuery])
  useEffect(() => {
    const ev = params.get('evento')
    if (ev) setAnalogQuery('')
  }, [params])

  return (
    <div>
      <div className="screen-head">
        <div>
          <h1>Archivo</h1>
          <div className="sub">Casos históricos codificados a mano: variables, desenlace, duración y fuentes. Alimentan las tasas base del motor de pronóstico.</div>
        </div>
      </div>
      <div className="two-col narrow-right">
        <div>
          <div className="filters">
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar caso…" aria-label="Buscar caso" />
            <select value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Categoría">
              <option value="">Todas las categorías</option>
              {data?.categories.map((c) => (
                <option key={c} value={c}>
                  {caseCategoryLabel(c)}
                </option>
              ))}
            </select>
            {data && <span className="muted small">{data.cases.length} casos</span>}
          </div>
          {loading && !data && <Loading />}
          <ErrorBox error={error} />
          {data && data.cases.length === 0 && <EmptyState title="Sin casos">Ejecuta `atlas seed` para cargar los 60 casos de semilla.</EmptyState>}
          {data && data.cases.length > 0 && (
            <DataTable
              rows={data.cases}
              rowKey={(c) => c.id}
              onRow={(c) => setParams({ caso: c.id }, { replace: true })}
              rowClass={(c) => (c.id === selectedId ? 'active' : undefined)}
              maxHeight="calc(100vh - 320px)"
              columns={[
                { key: 'name', label: 'Caso', render: (c) => <strong>{c.name}</strong>, sort: (c) => c.name },
                { key: 'cat', label: 'Categoría', render: (c) => caseCategoryLabel(c.category), sort: (c) => c.category, width: 160 },
                { key: 'start', label: 'Inicio', render: (c) => <span className="mono">{c.start_date}</span>, sort: (c) => c.start_date ?? '', width: 100 },
                { key: 'dur', label: 'Meses', num: true, render: (c) => c.duration_months ?? '—', sort: (c) => c.duration_months ?? 0, width: 70 },
                { key: 'countries', label: 'Países', render: (c) => <CountryChips countries={c.countries} max={4} link={false} />, width: 160 },
              ]}
            />
          )}
        </div>
        <div className="col">
          {selected ? <CaseSheet c={selected} /> : <EmptyState title="Elige un caso">La ficha aparece aquí con variables, desenlace y fuentes (con la nota de semilla cuando procede).</EmptyState>}
        </div>
      </div>

      <section className="section">
        <div className="section-head">
          <h2>Buscador de análogos</h2>
          <span className="muted small">similitud por embeddings locales sobre los casos codificados</span>
        </div>
        <div className="filters">
          <input type="search" value={aq} onChange={(e) => setAq(e.target.value)} placeholder="Describe la situación actual: «crisis de deuda soberana con salida de capitales y tipo fijo»…" aria-label="Situación a comparar" style={{ minWidth: 480 }} onKeyDown={(e) => e.key === 'Enter' && setAnalogQuery(aq)} />
          <button type="button" className="btn" onClick={() => setAnalogQuery(aq)} disabled={!aq.trim()}>
            Buscar análogos
          </button>
        </div>
        {analogs.loading && <Loading />}
        <ErrorBox error={analogs.error} />
        {analogs.data && (
          <>
            <p className="notice">{analogs.data.note}</p>
            <div className="biz-cards" style={{ marginBottom: 12 }}>
              {analogs.data.analogs.map((c) => (
                <Card key={c.id} title={c.name} extra={<span className="num">sim. {c.similarity?.toFixed(3)}</span>}>
                  <div className="small muted">
                    {caseCategoryLabel(c.category)} · {c.start_date?.slice(0, 4)}
                  </div>
                  <div className="small">{c.outcome}</div>
                  <button type="button" className="btn-link small" onClick={() => setParams({ caso: c.id }, { replace: true })}>
                    ver ficha
                  </button>
                </Card>
              ))}
            </div>
            {analogs.data.compare && (
              <>
                <h3 style={{ marginBottom: 6 }}>Similitudes y diferencias</h3>
                <CompareTable compare={analogs.data.compare} />
              </>
            )}
          </>
        )}
      </section>
    </div>
  )
}
