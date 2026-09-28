import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import type { MarketsResponse } from '../../api/types'
import { fmtPct, fmtPrice, fmtSignedPct, fmtTime } from '../../lib/format'
import { useInterval } from '../../lib/hooks'
import { Sparkline } from '../ui/basics'

const GROUP_ORDER = ['indices', 'fx', 'commodities', 'rates', 'crypto']

/** Cinta inferior: cotizaciones (GET /api/markets) y probabilidades de los mercados de predicción seguidos. */
export function MarketTicker() {
  const [data, setData] = useState<MarketsResponse | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const load = () =>
    api
      .markets()
      .then((d) => {
        setData(d)
        setErr(null)
      })
      .catch((e: Error) => setErr(e.message))
  useEffect(() => {
    void load()
  }, [])
  useInterval(load, 120000)

  const quotes = (data?.quotes ?? []).slice().sort((a, b) => GROUP_ORDER.indexOf(a.group_name) - GROUP_ORDER.indexOf(b.group_name))
  const followed = (data?.prediction_markets ?? []).filter((m) => m.followed)
  const items = (
    <>
      {quotes.map((q) => (
        <Link key={q.symbol} to="/mercados" className="q" title={`${q.label} · ${q.source ?? ''} · dato de ${fmtTime(q.observed_at)}${q.error ? ` · error: ${q.error}` : ''}`}>
          <span className="sym">{q.label}</span>
          {q.price == null ? (
            <span className="nodata">sin dato{q.error ? ` (${q.error.slice(0, 40)})` : ''}</span>
          ) : (
            <>
              <span className="px">{fmtPrice(q.price)}</span>
              <span className={`chg ${(q.change_pct ?? 0) > 0 ? 'up' : (q.change_pct ?? 0) < 0 ? 'down' : ''}`}>{fmtSignedPct(q.change_pct)}</span>
              <Sparkline values={q.history.map((h) => h.v)} width={48} height={14} baseline={false} />
            </>
          )}
          <span className="t">{fmtTime(q.observed_at)}</span>
        </Link>
      ))}
      {followed.map((m) => (
        <a key={m.id} className="q pm" href={m.url ?? undefined} target="_blank" rel="noopener noreferrer" title={`${m.question} · ${m.venue}`}>
          <span className="sym">{m.question.length > 48 ? `${m.question.slice(0, 48)}…` : m.question}</span>
          <span className="prob">{fmtPct(m.probability)}</span>
          <span className="t">{m.venue}</span>
        </a>
      ))}
    </>
  )
  const duration = Math.max(40, (quotes.length + followed.length) * 6)
  return (
    <footer className="ticker" aria-label="Cinta de mercados">
      <div className="disclaimer" title={data?.disclaimer ?? 'Información, no asesoramiento financiero'}>
        Información, no asesoramiento
      </div>
      {err && <div className="empty-note">Cinta sin datos: {err}</div>}
      {!err && data && quotes.length === 0 && (
        <div className="empty-note">
          Sin cotizaciones todavía. Lanza «Actualizar mercados» en la <Link to="/maquinas">Sala de máquinas</Link>.
        </div>
      )}
      {quotes.length > 0 && (
        <div className="track">
          <div className="lane" style={{ '--ticker-duration': `${duration}s` } as React.CSSProperties}>
            {items}
            {items}
          </div>
        </div>
      )}
    </footer>
  )
}
