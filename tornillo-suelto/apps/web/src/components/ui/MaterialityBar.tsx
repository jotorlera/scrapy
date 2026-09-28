import type { MaterialityBreakdown } from '../../api/types'
import { featureLabel } from '../../lib/labels'
import { fmt1, fmt2, seqColor } from '../../lib/format'
import { InfoIcon } from './basics'

/** Barra de materialidad (0-100) en escala secuencial de un solo tono, con ⓘ de desglose. */
export function MaterialityBar({ value, breakdown, compact = false }: { value: number | null | undefined; breakdown?: MaterialityBreakdown | null; compact?: boolean }) {
  const v = value ?? 0
  return (
    <span className="mat" title={`Materialidad ${fmt1(v)} / 100`}>
      <span className="bar" style={compact ? { width: 48 } : undefined}>
        <i style={{ width: `${Math.min(100, Math.max(0, v))}%`, background: seqColor(v / 100) }} />
      </span>
      <span className="val">{fmt1(v)}</span>
      {breakdown && (
        <InfoIcon label="Desglose de la materialidad">
          <Breakdown breakdown={breakdown} />
        </InfoIcon>
      )}
    </span>
  )
}

export function Breakdown({ breakdown }: { breakdown: MaterialityBreakdown }) {
  const contribs = Object.entries(breakdown.contributions ?? {})
  const maxAbs = Math.max(0.01, ...contribs.map(([, v]) => Math.abs(v)))
  return (
    <div>
      <h4>Materialidad {fmt1(breakdown.score)} · desglose</h4>
      <div className="muted small" style={{ marginBottom: 6 }}>
        {breakdown.method} · β₀ = {fmt2(breakdown.beta0)}
      </div>
      {contribs.map(([k, v]) => (
        <div key={k} className="breakdown-row">
          <span className="truncate" title={`${featureLabel(k)} · rasgo ${fmt2(breakdown.features?.[k.replace('_penalty', '')] ?? 0)}`}>
            {featureLabel(k)}
          </span>
          <span className="bar">
            <i style={{ width: `${(Math.abs(v) / maxAbs) * 100}%`, background: v < 0 ? 'var(--c-warn)' : undefined }} />
          </span>
          <span className="num right">{v >= 0 ? '+' : ''}{fmt2(v)}</span>
        </div>
      ))}
      <div className="small" style={{ marginTop: 6 }}>
        Bonificación del perfil: <span className="num">+{fmt2(breakdown.user_bonus_points)}</span>
        {breakdown.user_reasons?.length ? <span className="muted"> ({breakdown.user_reasons.join('; ')})</span> : null}
      </div>
      <div className="small muted">
        {breakdown.n_docs} documentos · {breakdown.n_independent_sources} fuentes independientes · bloques: {breakdown.blocs?.join(', ') || '—'}
      </div>
    </div>
  )
}
