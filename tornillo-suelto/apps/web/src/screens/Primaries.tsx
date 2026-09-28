import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { DiffResponse, DocumentOut, PrimariesResponse } from '../api/types'
import { Card, EmptyState, ErrorBox, ExtLink, Loading } from '../components/ui/basics'
import { DataTable } from '../components/ui/DataTable'
import { fmtDateTime } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { docKindLabel, sourceTypeLabel } from '../lib/labels'
import { useStore } from '../state/store'
import './screens.css'

function OpCell({ op, side }: { op: DiffResponse['ops'][number]; side: 'old' | 'new' }) {
  const text = side === 'old' ? op.old : op.new
  if (text == null) return <div className="op empty" />
  if (op.op === 'replace' && op.inline) {
    return (
      <div className="op replace">
        {op.inline.map((seg, i) => {
          if (seg.t === 'eq') return <span key={i}>{seg.s} </span>
          if (seg.t === 'del' && side === 'old') return <del key={i}>{seg.s} </del>
          if (seg.t === 'ins' && side === 'new') return <ins key={i}>{seg.s} </ins>
          return null
        })}
      </div>
    )
  }
  return <div className={`op ${op.op}`}>{text}</div>
}

export default function Primaries() {
  const [params, setParams] = useSearchParams()
  const source = params.get('fuente') ?? ''
  const country = params.get('pais') ?? ''
  const kind = params.get('tipo') ?? ''
  const hours = Number(params.get('h') ?? 720)
  const { setPanel } = useStore()
  const set = (k: string, v: string) => {
    const p = new URLSearchParams(params)
    if (v) p.set(k, v)
    else p.delete(k)
    setParams(p, { replace: true })
  }
  const { data, error, loading } = useAsync<PrimariesResponse>(() => api.primaries({ hours, source_slug: source || undefined, country: country || undefined, kind: kind || undefined, limit: 200 }), [hours, source, country, kind])

  // Linajes: elegir dos documentos de la misma institución
  const [lineage, setLineage] = useState('')
  const [lineageDocs, setLineageDocs] = useState<DocumentOut[]>([])
  const [oldId, setOldId] = useState('')
  const [newId, setNewId] = useState('')
  useEffect(() => {
    if (!lineage) {
      setLineageDocs([])
      return
    }
    api
      .primaries({ hours: 24 * 365, source_slug: lineage, limit: 60 })
      .then((r) => {
        setLineageDocs(r.documents)
        if (r.documents.length >= 2) {
          setNewId(r.documents[0].id)
          setOldId(r.documents[1].id)
        }
      })
      .catch(() => setLineageDocs([]))
  }, [lineage])
  const diff = useAsync<DiffResponse | null>(() => (oldId && newId && oldId !== newId ? api.diff(oldId, newId) : Promise.resolve(null)), [oldId, newId])

  const countries = useMemo(() => Array.from(new Set((data?.sources ?? []).map((s) => s.country).filter(Boolean))).sort() as string[], [data])
  const kinds = useMemo(() => Array.from(new Set((data?.documents ?? []).map((d) => d.kind))).sort(), [data])

  return (
    <div>
      <div className="screen-head">
        <div>
          <h1>Primarias</h1>
          <div className="sub">Documentos oficiales (fuentes de tier 1) antes que su interpretación. Elige dos del mismo linaje para ver qué cambia.</div>
        </div>
      </div>
      <div className="filters">
        <select value={source} onChange={(e) => set('fuente', e.target.value)} aria-label="Fuente">
          <option value="">Todas las fuentes</option>
          {data?.sources.map((s) => (
            <option key={s.slug} value={s.slug}>
              {s.name} ({s.n})
            </option>
          ))}
        </select>
        <select value={country} onChange={(e) => set('pais', e.target.value)} aria-label="País">
          <option value="">Todos los países</option>
          {countries.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select value={kind} onChange={(e) => set('tipo', e.target.value)} aria-label="Tipo">
          <option value="">Todos los tipos</option>
          {kinds.map((k) => (
            <option key={k} value={k}>
              {docKindLabel(k)}
            </option>
          ))}
        </select>
        <div className="seg">
          {[168, 720, 2160].map((h) => (
            <button key={h} type="button" aria-pressed={hours === h} onClick={() => set('h', String(h))}>
              {h === 168 ? '7 d' : h === 720 ? '30 d' : '90 d'}
            </button>
          ))}
        </div>
        {data && <span className="muted small">{data.documents.length} documentos</span>}
      </div>
      {loading && !data && <Loading />}
      <ErrorBox error={error} />

      <div className="two-col narrow-right">
        <div>
          {data && data.documents.length === 0 && <EmptyState title="Sin documentos primarios en la ventana">Amplía la ventana o revisa en la Sala de máquinas si las fuentes de tier 1 tienen feed y último OK.</EmptyState>}
          {data && data.documents.length > 0 && (
            <DataTable
              rows={data.documents}
              rowKey={(d) => d.id}
              onRow={(d) => setPanel({ kind: 'document', id: d.id })}
              maxHeight="calc(100vh - 300px)"
              columns={[
                { key: 'when', label: 'Hora', render: (d) => <span className="mono">{fmtDateTime(d.published_at)}</span>, sort: (d) => d.published_at ?? '', width: 110 },
                { key: 'src', label: 'Fuente', render: (d) => <span>{d.source_name}</span>, sort: (d) => d.source_name ?? '', width: 160 },
                { key: 'kind', label: 'Tipo', render: (d) => <span className="chip">{docKindLabel(d.kind)}</span>, sort: (d) => d.kind, width: 130 },
                {
                  key: 'title',
                  label: 'Documento',
                  render: (d) => (
                    <>
                      <div>{d.title}</div>
                      <div className="muted small row wrap">
                        <span>{sourceTypeLabel(d.source_type)}</span>
                        <span className="mono">{d.source_country}</span>
                        {d.event_id && (
                          <Link to={`/eventos/${d.event_id}`} onClick={(e) => e.stopPropagation()}>
                            evento
                          </Link>
                        )}
                        <ExtLink href={d.url}>original ↗</ExtLink>
                      </div>
                    </>
                  ),
                },
              ]}
            />
          )}
        </div>
        <div className="col">
          <Card title="Linajes" extra={<span className="muted small">instituciones con ≥ 2 documentos</span>}>
            <select value={lineage} onChange={(e) => setLineage(e.target.value)} aria-label="Institución" style={{ width: '100%' }}>
              <option value="">Elige una institución…</option>
              {data?.lineages.map((l) => (
                <option key={l.slug} value={l.slug}>
                  {l.name} ({l.n})
                </option>
              ))}
            </select>
            {lineageDocs.length >= 2 && (
              <div className="col" style={{ marginTop: 8 }}>
                <label className="field">
                  Versión anterior
                  <select value={oldId} onChange={(e) => setOldId(e.target.value)}>
                    {lineageDocs.map((d) => (
                      <option key={d.id} value={d.id}>
                        {fmtDateTime(d.published_at)} · {d.title?.slice(0, 70)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  Versión nueva
                  <select value={newId} onChange={(e) => setNewId(e.target.value)}>
                    {lineageDocs.map((d) => (
                      <option key={d.id} value={d.id}>
                        {fmtDateTime(d.published_at)} · {d.title?.slice(0, 70)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            )}
            {lineage && lineageDocs.length < 2 && <p className="muted small">No hay dos documentos de esta institución.</p>}
          </Card>
          {diff.loading && <Loading text="Calculando diff…" />}
          <ErrorBox error={diff.error} />
          {diff.data && (
            <Card title="Resumen del DIFF" extra={<span className="muted small">{diff.data.method}</span>}>
              <p>{diff.data.summary}</p>
              <div className="small muted">
                similitud {diff.data.ratio} · {diff.data.n_old} → {diff.data.n_new} frases · {diff.data.n_changed} cambian
              </div>
              {diff.data.material_changes.length > 0 && (
                <>
                  <div className="label" style={{ marginTop: 8 }}>
                    Cambios materiales (cifras o compromisos)
                  </div>
                  <ul style={{ margin: '4px 0 0 16px', padding: 0, fontSize: 'var(--fs-data)' }}>
                    {diff.data.material_changes.map((m, i) => (
                      <li key={i}>
                        <span className="chip">{m.kind === 'added' ? 'añadido' : m.kind === 'removed' ? 'eliminado' : 'modificado'}</span> {m.new ?? m.old}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </Card>
          )}
        </div>
      </div>

      {diff.data && (
        <section className="section">
          <div className="section-head">
            <h2>DIFF</h2>
            <span className="muted small">
              <ExtLink href={diff.data.old.url}>{diff.data.old.title}</ExtLink> → <ExtLink href={diff.data.new.url}>{diff.data.new.title}</ExtLink>
            </span>
          </div>
          <div className="diff">
            <div className="dcol">
              <div className="dhead">
                <strong>Anterior</strong> <span className="muted mono small">{fmtDateTime(diff.data.old.published_at)}</span>
              </div>
              {diff.data.ops.map((op, i) => (
                <OpCell key={i} op={op} side="old" />
              ))}
            </div>
            <div className="dcol">
              <div className="dhead">
                <strong>Nuevo</strong> <span className="muted mono small">{fmtDateTime(diff.data.new.published_at)}</span>
              </div>
              {diff.data.ops.map((op, i) => (
                <OpCell key={i} op={op} side="new" />
              ))}
            </div>
          </div>
        </section>
      )}
    </div>
  )
}
