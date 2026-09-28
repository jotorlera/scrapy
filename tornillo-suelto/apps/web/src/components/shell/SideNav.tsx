import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { api } from '../../api/client'
import { COMMON_NAV, MODE_NAV, useStore } from '../../state/store'

export function SideNav() {
  const { mode, agents } = useStore()
  const [health, setHealth] = useState<{ counts: Record<string, number>; version: string } | null>(null)
  useEffect(() => {
    api.health().then((h) => setHealth({ counts: h.counts, version: h.version })).catch(() => undefined)
  }, [])
  return (
    <nav className="nav" aria-label="Navegación del modo">
      <div className="mode-title label">{mode}</div>
      {MODE_NAV[mode].map((item) => (
        <NavLink key={item.to} to={item.to} end={item.to === '/'} className={({ isActive }) => (isActive ? 'active' : '')}>
          <span>{item.label}</span>
          <kbd>g {item.key}</kbd>
        </NavLink>
      ))}
      <div className="spacer" />
      <div className="common">
        {COMMON_NAV.map((item) => (
          <NavLink key={item.to} to={item.to} className={({ isActive }) => (isActive ? 'active' : '')}>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </div>
      <div className="status-line" title="Estado del motor">
        {health ? `${health.counts.events} ev · ${health.counts.documents} doc · ${health.counts.claims} afirm.` : 'API…'}
        <br />
        {agents ? (agents.enabled ? `agentes ON · ${agents.spent_today_usd.toFixed(2)}/${agents.daily_cap_usd} USD` : 'agentes OFF (sin clave)') : ''}
        {health && (
          <>
            <br />
            ATLAS v{health.version}
          </>
        )}
      </div>
    </nav>
  )
}
