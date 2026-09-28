import { useState, type ReactNode } from 'react'

/** Muestra la cita literal (y su fuente) al pasar el ratón o al enfocar. */
export function QuoteHover({ quote, source, children }: { quote: string | null | undefined; source?: ReactNode; children: ReactNode }) {
  const [show, setShow] = useState(false)
  if (!quote) return <>{children}</>
  return (
    <span className="quote-hover" onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)} onFocus={() => setShow(true)} onBlur={() => setShow(false)}>
      {children}
      {show && (
        <span className="quote-tip" role="tooltip">
          «{quote}»{source && <span className="src">{source}</span>}
        </span>
      )}
    </span>
  )
}
