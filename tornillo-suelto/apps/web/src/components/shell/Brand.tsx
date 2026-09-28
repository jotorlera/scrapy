import { Link } from 'react-router-dom'

/** Tornillo ligeramente torcido, en amarillo. Icono propio (SVG inline). */
export function ScrewIcon({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <g transform="rotate(12 16 16)">
        <rect x="9" y="4" width="14" height="6" fill="#FFD100" />
        <rect x="14.5" y="5.5" width="3" height="3" fill="var(--c-black)" />
        <path d="M12 10 L20 10 L18 27 L14 27 Z" fill="#FFD100" />
        <g stroke="var(--c-black)" strokeWidth="1.2">
          <line x1="12.6" y1="14" x2="19.4" y2="14" />
          <line x1="12.9" y1="17.5" x2="19.1" y2="17.5" />
          <line x1="13.2" y1="21" x2="18.8" y2="21" />
          <line x1="13.6" y1="24.5" x2="18.4" y2="24.5" />
        </g>
      </g>
    </svg>
  )
}

export function Brand() {
  return (
    <Link to="/" className="brand" title="TORNILLO SUELTO · ir al Radar">
      <ScrewIcon />
      <span>
        <div className="name">TORNILLO SUELTO</div>
        <div className="tag">motor ATLAS · inteligencia global con un tornillo de menos</div>
      </span>
    </Link>
  )
}
