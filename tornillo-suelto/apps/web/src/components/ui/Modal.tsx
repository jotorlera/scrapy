import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

/** Modal accesible: cierra con Escape o clic en el fondo; devuelve el foco al cerrar. */
export function Modal({ open, title, onClose, children, wide = false, initialFocus = true }: { open: boolean; title: ReactNode; onClose: () => void; children: ReactNode; wide?: boolean; initialFocus?: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const prev = document.activeElement as HTMLElement | null
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onClose()
      }
    }
    document.addEventListener('keydown', onKey, true)
    if (initialFocus) {
      const first = ref.current?.querySelector<HTMLElement>('input, textarea, select, button:not(.modal-close)')
      first?.focus()
    }
    return () => {
      document.removeEventListener('keydown', onKey, true)
      prev?.focus?.()
    }
  }, [open, onClose, initialFocus])
  if (!open) return null
  return createPortal(
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true" ref={ref}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button type="button" className="btn-icon modal-close" onClick={onClose} aria-label="Cerrar">
            ✕
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>,
    document.body,
  )
}
