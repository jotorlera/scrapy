import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import type { AlertsResponse, Mode } from '../../api/types'
import { fmtAgo } from '../../lib/format'
import { useInterval } from '../../lib/hooks'
import { MODE_NAV, useStore } from '../../state/store'
import { Brand } from './Brand'

const MODES: Mode[] = ['ANALISTA', 'PENSADOR', 'CEO']

export function Header() {
  const { mode, setMode, theme, toggleTheme, settings, setSetting, setPaletteOpen, setHelpOpen } = useStore()
  const nav = useNavigate()
  const [alerts, setAlerts] = useState<AlertsResponse | null>(null)
  const [alertsOpen, setAlertsOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const menusRef = useRef<HTMLDivElement>(null)

  const loadAlerts = () => api.alerts().then(setAlerts).catch(() => undefined)
  useEffect(() => {
    void loadAlerts()
  }, [])
  useInterval(loadAlerts, 60000)

  useEffect(() => {
    if (!alertsOpen && !settingsOpen) return
    const onDoc = (e: MouseEvent) => {
      if (menusRef.current && !menusRef.current.contains(e.target as Node)) {
        setAlertsOpen(false)
        setSettingsOpen(false)
      }
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [alertsOpen, settingsOpen])

  const changeMode = (m: Mode) => {
    setMode(m)
    nav(MODE_NAV[m][0].to)
  }

  const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)

  return (
    <header className="header">
      <Brand />
      <div className="mode-switch" role="group" aria-label="Modo">
        {MODES.map((m, i) => (
          <button key={m} type="button" aria-pressed={mode === m} onClick={() => changeMode(m)} title={`Modo ${m} (tecla ${i + 1})`}>
            {m}
          </button>
        ))}
      </div>
      <button type="button" className="search-box" onClick={() => setPaletteOpen(true)} aria-label="Abrir la paleta de búsqueda y acciones">
        <span aria-hidden="true">⌕</span>
        <span>Buscar / preguntar…</span>
        <kbd>{isMac ? '⌘' : 'Ctrl'} K</kbd>
      </button>
      <div className="header-right" ref={menusRef}>
        <button
          type="button"
          className="btn-icon bell"
          aria-label={`Alertas${alerts?.unread ? `, ${alerts.unread} sin leer` : ''}`}
          onClick={() => {
            setAlertsOpen((o) => !o)
            setSettingsOpen(false)
          }}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M8 1.5a4 4 0 0 0-4 4v3L2.5 11h11L12 8.5v-3a4 4 0 0 0-4-4Z" fill="none" stroke="currentColor" strokeWidth="1.3" />
            <path d="M6.5 13a1.5 1.5 0 0 0 3 0" fill="none" stroke="currentColor" strokeWidth="1.3" />
          </svg>
          {alerts && alerts.unread > 0 && <span className="badge">{alerts.unread}</span>}
        </button>
        <Link to="/brief" className="brief-link" title="Brief diario">
          <span className="mono">{settings.brief_hour}</span> Brief
        </Link>
        <button type="button" className="btn-icon" onClick={toggleTheme} aria-label={theme === 'dark' ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'} title={theme === 'dark' ? 'Tema claro' : 'Tema oscuro'}>
          {theme === 'dark' ? (
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <circle cx="8" cy="8" r="3.2" fill="none" stroke="currentColor" strokeWidth="1.3" />
              <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.4 1.4M11.6 11.6 13 13M3 13l1.4-1.4M11.6 4.4 13 3" stroke="currentColor" strokeWidth="1.3" />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <path d="M10.5 2a6 6 0 1 0 3.5 9.5A6.5 6.5 0 0 1 10.5 2Z" fill="none" stroke="currentColor" strokeWidth="1.3" />
            </svg>
          )}
        </button>
        <button
          type="button"
          className="btn-icon"
          aria-label="Ajustes"
          title="Ajustes"
          aria-expanded={settingsOpen}
          onClick={() => {
            setSettingsOpen((o) => !o)
            setAlertsOpen(false)
          }}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" strokeWidth="1.3" />
            <rect x="4" y="2.5" width="3" height="3" fill="var(--c-accent)" stroke="currentColor" strokeWidth="1" />
            <rect x="9" y="6.5" width="3" height="3" fill="var(--c-accent)" stroke="currentColor" strokeWidth="1" />
            <rect x="5" y="10.5" width="3" height="3" fill="var(--c-accent)" stroke="currentColor" strokeWidth="1" />
          </svg>
        </button>

        {alertsOpen && (
          <div className="alerts-menu" role="dialog" aria-label="Alertas">
            <div className="row" style={{ justifyContent: 'space-between', padding: '6px 10px', borderBottom: '1px solid var(--c-line)' }}>
              <strong>Alertas</strong>
              <button
                type="button"
                className="btn btn-sm btn-ghost"
                onClick={() => {
                  void api.alertsRead().then(loadAlerts)
                }}
                disabled={!alerts?.unread}
              >
                Marcar leídas
              </button>
            </div>
            {alerts?.alerts.length === 0 && alerts.high_materiality.length === 0 && <div className="item muted">Sin alertas. Se generan por umbral de materialidad, variables de estado, palabras clave del perfil y exposición de negocio.</div>}
            {alerts?.alerts.map((a) => (
              <div key={a.id} className={`item ${a.read ? '' : 'unread'}`}>
                <div className="row" style={{ justifyContent: 'space-between' }}>
                  <span className="label">{a.kind}</span>
                  <span className="muted mono">{fmtAgo(a.created_at)}</span>
                </div>
                <div>
                  {typeof a.ref.event_id === 'string' ? (
                    <Link to={`/eventos/${a.ref.event_id}`} onClick={() => setAlertsOpen(false)}>
                      {a.title}
                    </Link>
                  ) : (
                    a.title
                  )}
                </div>
                {a.body && <div className="muted">{a.body}</div>}
              </div>
            ))}
            {alerts && alerts.high_materiality.length > 0 && (
              <>
                <div className="label" style={{ padding: '6px 10px 2px' }}>
                  Materialidad ≥ 80 (24 h)
                </div>
                {alerts.high_materiality.map((e) => (
                  <div key={e.id} className="item">
                    <Link to={`/eventos/${e.id}`} onClick={() => setAlertsOpen(false)}>
                      {e.title_neutral}
                    </Link>
                  </div>
                ))}
              </>
            )}
          </div>
        )}

        {settingsOpen && (
          <div className="settings-menu" role="dialog" aria-label="Ajustes">
            <strong>Ajustes</strong>
            <label className="opt">
              <span>Densidad</span>
              <span className="seg">
                <button type="button" aria-pressed={settings.density === 'compact'} onClick={() => setSetting('density', 'compact')}>
                  Compacta
                </button>
                <button type="button" aria-pressed={settings.density === 'comfortable'} onClick={() => setSetting('density', 'comfortable')}>
                  Cómoda
                </button>
              </span>
            </label>
            <label className="opt">
              <span>Tema</span>
              <span className="seg">
                <button type="button" aria-pressed={theme === 'light'} onClick={() => setSetting('theme', 'light')}>
                  Claro
                </button>
                <button type="button" aria-pressed={theme === 'dark'} onClick={() => setSetting('theme', 'dark')}>
                  Oscuro
                </button>
              </span>
            </label>
            <label className="opt">
              <span>Tuerca, la gata</span>
              <span className="seg">
                <button type="button" aria-pressed={settings.cat_enabled} onClick={() => setSetting('cat_enabled', true)}>
                  Activa
                </button>
                <button type="button" aria-pressed={!settings.cat_enabled} onClick={() => setSetting('cat_enabled', false)}>
                  Dormida
                </button>
              </span>
            </label>
            <label className="opt">
              <span>Modo de inicio</span>
              <select value={settings.mode} onChange={(e) => setSetting('mode', e.target.value as Mode)}>
                {MODES.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </label>
            <div className="opt">
              <span>Hora del brief</span>
              <span className="mono">{settings.brief_hour}</span>
            </div>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <button type="button" className="btn-link" onClick={() => setHelpOpen(true)}>
                Atajos de teclado (?)
              </button>
              <Link to="/maquinas" onClick={() => setSettingsOpen(false)}>
                Sala de máquinas
              </Link>
            </div>
            <div className="muted small">Los ajustes se guardan en la base local (PUT /api/settings). La gata respeta prefers-reduced-motion.</div>
          </div>
        )}
      </div>
    </header>
  )
}
