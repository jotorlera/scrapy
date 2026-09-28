/* Piezas pequeñas: Card, Chip, StatusIcon, Level, Loading, ErrorBox, EmptyState, Tabs, Sparkline, Popover, InfoIcon. */

import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { domainColor, domainLabel, extractorLabel, levelLabel, STATUS_GLYPH, STATUS_LABEL, statusKind, titleSourceLabel } from '../../lib/labels'
import './ui.css'

export function Card({ title, extra, children, className = '', surface = false, style }: { title?: ReactNode; extra?: ReactNode; children: ReactNode; className?: string; surface?: boolean; style?: CSSProperties }) {
  return (
    <section className={`card ${surface ? 'surface' : ''} ${className}`} style={style}>
      {(title || extra) && (
        <div className="card-head">
          {title ? <h3>{title}</h3> : <span />}
          {extra}
        </div>
      )}
      {children}
    </section>
  )
}

export function Chip({ children, kind = '', title, onClick, style }: { children: ReactNode; kind?: string; title?: string; onClick?: () => void; style?: CSSProperties }) {
  const cls = `chip ${kind} ${onClick ? 'clickable' : ''}`
  if (onClick)
    return (
      <button type="button" className={cls} title={title} onClick={onClick} style={style}>
        {children}
      </button>
    )
  return (
    <span className={cls} title={title} style={style}>
      {children}
    </span>
  )
}

export function DomainChip({ domain }: { domain: string | null | undefined }) {
  return (
    <span className="chip dom" style={{ '--dom-color': domainColor(domain) } as CSSProperties}>
      {domainLabel(domain)}
    </span>
  )
}

export function CountryChips({ countries, max = 4, link = true }: { countries: string[]; max?: number; link?: boolean }) {
  const shown = countries.slice(0, max)
  const rest = countries.length - shown.length
  return (
    <span className="row" style={{ gap: 3, display: 'inline-flex' }}>
      {shown.map((c) =>
        link ? (
          <Link key={c} to={`/paises/${c}`} className="chip mono" title={`Ficha de ${c}`} onClick={(e) => e.stopPropagation()}>
            {c}
          </Link>
        ) : (
          <span key={c} className="chip mono">
            {c}
          </span>
        ),
      )}
      {rest > 0 && <span className="chip mono">+{rest}</span>}
    </span>
  )
}

export function StatusIcon({ status, withLabel = true }: { status: string | null | undefined; withLabel?: boolean }) {
  const k = statusKind(status)
  return (
    <span className="status" data-kind={k} title={STATUS_LABEL[k]}>
      <i aria-hidden="true">{STATUS_GLYPH[k]}</i>
      {withLabel ? STATUS_LABEL[k] : <span className="sr-only">{STATUS_LABEL[k]}</span>}
    </span>
  )
}

export function Level({ level }: { level: string }) {
  return (
    <span className="level" data-level={level}>
      {levelLabel(level)}
    </span>
  )
}

export function ProvenanceChip({ titleSource, extractedBy, composedBy }: { titleSource?: string | null; extractedBy?: string | null; composedBy?: string | null }) {
  let text = ''
  if (titleSource !== undefined) text = titleSourceLabel(titleSource)
  else if (extractedBy !== undefined) text = extractorLabel(extractedBy)
  else if (composedBy !== undefined) text = composedBy ?? ''
  return (
    <span className="chip provenance" title="Procedencia">
      {text}
    </span>
  )
}

export function Loading({ text = 'Cargando…' }: { text?: string }) {
  return (
    <div className="loading" role="status">
      {text}
    </div>
  )
}

export function ErrorBox({ error, retry }: { error: Error | ApiError | null; retry?: () => void }) {
  if (!error) return null
  const msg = error instanceof ApiError ? error.userMessage : error.message
  const status = error instanceof ApiError ? error.status : null
  return (
    <div className="errorbox" role="alert">
      <b>Error{status ? ` ${status}` : ''}.</b> {msg}
      {status === 0 || msg.includes('Failed to fetch') ? <div className="muted">¿Está arrancada la API? `make api` o `uvicorn atlas_core.api.app:app --port 8765`.</div> : null}
      {retry && (
        <div style={{ marginTop: 6 }}>
          <button type="button" className="btn btn-sm btn-ghost" onClick={retry}>
            Reintentar
          </button>
        </div>
      )}
    </div>
  )
}

export function EmptyState({ title, children, actions }: { title: string; children?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      {children}
      {actions && <div className="actions">{actions}</div>}
    </div>
  )
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: Array<{ id: T; label: string; count?: number }>; value: T; onChange: (t: T) => void }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} type="button" role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}>
          {t.label}
          {t.count !== undefined && <span className="count">{t.count}</span>}
        </button>
      ))}
    </div>
  )
}

export function Sparkline({ values, width = 64, height = 18, stroke = 'currentColor', baseline = true }: { values: number[]; width?: number; height?: number; stroke?: string; baseline?: boolean }) {
  if (!values || values.length < 2) return <span className="muted small">—</span>
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const pts = values.map((v, i) => `${((i / (values.length - 1)) * (width - 2) + 1).toFixed(1)},${(height - 1 - ((v - min) / span) * (height - 2)).toFixed(1)}`)
  const first = height - 1 - ((values[0] - min) / span) * (height - 2)
  return (
    <svg className="spark" width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      {baseline && <line x1={0} x2={width} y1={first} y2={first} stroke="var(--c-line)" strokeWidth={1} />}
      <polyline points={pts.join(' ')} fill="none" stroke={stroke} strokeWidth={1.2} />
      <circle cx={pts[pts.length - 1].split(',')[0]} cy={pts[pts.length - 1].split(',')[1]} r={1.6} fill="var(--c-accent)" stroke="var(--c-black)" strokeWidth={0.6} />
    </svg>
  )
}

/** Popover controlado por un botón; se cierra con Escape o clic fuera. */
export function Popover({ button, children, align = 'left', label }: { button: ReactNode; children: ReactNode; align?: 'left' | 'right'; label?: string }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)
  const id = useId()
  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])
  return (
    <span className="popover-anchor" ref={ref}>
      <button
        type="button"
        className="info-btn"
        aria-expanded={open}
        aria-controls={id}
        aria-label={label ?? 'Ver desglose'}
        title={label ?? 'Ver desglose'}
        onClick={(e) => {
          e.stopPropagation()
          e.preventDefault()
          setOpen((o) => !o)
        }}
      >
        {button}
      </button>
      {open && (
        <div className={`popover ${align}`} id={id} role="dialog" onClick={(e) => e.stopPropagation()}>
          {children}
        </div>
      )}
    </span>
  )
}

export function InfoIcon({ children, align = 'left', label }: { children: ReactNode; align?: 'left' | 'right'; label?: string }) {
  return (
    <Popover button={<span aria-hidden="true">i</span>} align={align} label={label}>
      {children}
    </Popover>
  )
}

export function Kv({ rows }: { rows: Array<[string, ReactNode]> }) {
  return (
    <dl className="kv">
      {rows.map(([k, v]) => (
        <div key={k} style={{ display: 'contents' }}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  )
}

export function ExtLink({ href, children, title }: { href: string | null | undefined; children: ReactNode; title?: string }) {
  if (!href) return <>{children}</>
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" title={title ?? href}>
      {children}
    </a>
  )
}
