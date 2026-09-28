/* Estado global mínimo: ajustes (tema, modo, densidad, gata), estado de agentes, selección y panel contextual. */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api } from '../api/client'
import type { AgentsStatus, EventSummary, Mode, Settings } from '../api/types'

export type PanelContent =
  | { kind: 'document'; id: string; highlight?: string | null }
  | { kind: 'agent-stream'; title: string; url: string; method?: 'GET' | 'POST'; body?: unknown; key: string }
  | { kind: 'agent-result'; title: string; result: unknown; resultKind: 'red_team' | 'normative' | 'generic' }
  | { kind: 'event'; event: EventSummary }
  | null

interface StoreValue {
  settings: Settings
  settingsLoaded: boolean
  setSetting: <K extends keyof Settings>(key: K, value: Settings[K]) => void
  mode: Mode
  setMode: (m: Mode) => void
  theme: 'light' | 'dark'
  toggleTheme: () => void
  agents: AgentsStatus | null
  agentsEnabled: boolean
  refreshAgents: () => void
  currentEvent: EventSummary | null
  setCurrentEvent: (e: EventSummary | null) => void
  panel: PanelContent
  setPanel: (p: PanelContent) => void
  panelOpen: boolean
  setPanelOpen: (open: boolean) => void
  paletteOpen: boolean
  setPaletteOpen: (open: boolean) => void
  helpOpen: boolean
  setHelpOpen: (open: boolean) => void
  toast: (msg: string, kind?: 'ok' | 'warn') => void
  toasts: Array<{ id: number; msg: string; kind: 'ok' | 'warn' }>
}

const DEFAULTS: Settings = { theme: 'light', mode: 'ANALISTA', cat_enabled: true, density: 'compact', brief_hour: '07:00' }

const StoreCtx = createContext<StoreValue | null>(null)

export function StoreProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(DEFAULTS)
  const [settingsLoaded, setLoaded] = useState(false)
  // Modo de la sesión: arranca en el «modo de inicio» guardado y cambia al navegar, sin tocar el ajuste.
  const [mode, setModeState] = useState<Mode>(DEFAULTS.mode)
  const [agents, setAgents] = useState<AgentsStatus | null>(null)
  const [currentEvent, setCurrentEvent] = useState<EventSummary | null>(null)
  const [panel, setPanelState] = useState<PanelContent>(null)
  const [panelOpen, setPanelOpen] = useState(() => window.innerWidth >= 1600)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [toasts, setToasts] = useState<Array<{ id: number; msg: string; kind: 'ok' | 'warn' }>>([])
  const toastId = useRef(0)

  useEffect(() => {
    api
      .settings()
      .then((s) => {
        setSettings({ ...DEFAULTS, ...s })
        if (s.mode) setModeState(s.mode)
      })
      .catch(() => undefined)
      .finally(() => setLoaded(true))
  }, [])

  const refreshAgents = useCallback(() => {
    api
      .agentsStatus()
      .then(setAgents)
      .catch(() => setAgents(null))
  }, [])
  useEffect(() => {
    refreshAgents()
  }, [refreshAgents])

  // Aplicar tema y densidad al documento
  useEffect(() => {
    const root = document.documentElement
    root.setAttribute('data-theme', settings.theme)
    root.setAttribute('data-density', settings.density)
  }, [settings.theme, settings.density])

  const setSetting = useCallback(<K extends keyof Settings>(key: K, value: Settings[K]) => {
    setSettings((s) => ({ ...s, [key]: value }))
    void api.putSettings({ [key]: value } as Partial<Settings>).catch(() => undefined)
  }, [])

  const toast = useCallback((msg: string, kind: 'ok' | 'warn' = 'ok') => {
    const id = ++toastId.current
    setToasts((t) => [...t, { id, msg, kind }])
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000)
  }, [])

  const setPanel = useCallback((p: PanelContent) => {
    setPanelState(p)
    if (p) setPanelOpen(true)
  }, [])

  const value = useMemo<StoreValue>(
    () => ({
      settings,
      settingsLoaded,
      setSetting,
      mode,
      setMode: setModeState,
      theme: settings.theme,
      toggleTheme: () => setSetting('theme', settings.theme === 'dark' ? 'light' : 'dark'),
      agents,
      agentsEnabled: !!agents?.enabled,
      refreshAgents,
      currentEvent,
      setCurrentEvent,
      panel,
      setPanel,
      panelOpen,
      setPanelOpen,
      paletteOpen,
      setPaletteOpen,
      helpOpen,
      setHelpOpen,
      toast,
      toasts,
    }),
    [settings, settingsLoaded, setSetting, mode, agents, refreshAgents, currentEvent, panel, setPanel, panelOpen, paletteOpen, helpOpen, toast, toasts],
  )
  return <StoreCtx.Provider value={value}>{children}</StoreCtx.Provider>
}

export function useStore(): StoreValue {
  const v = useContext(StoreCtx)
  if (!v) throw new Error('useStore fuera de StoreProvider')
  return v
}

export const MODE_NAV: Record<Mode, Array<{ to: string; label: string; key: string }>> = {
  ANALISTA: [
    { to: '/', label: 'Radar', key: 'r' },
    { to: '/eventos', label: 'Eventos', key: 'e' },
    { to: '/prisma', label: 'Prisma', key: 'p' },
    { to: '/primarias', label: 'Primarias', key: 'i' },
    { to: '/mercados', label: 'Economía / Mercados', key: 'm' },
    { to: '/paises', label: 'Geopolítica / Países', key: 'g' },
    { to: '/actores', label: 'Actores', key: 'o' },
  ],
  PENSADOR: [
    { to: '/agora', label: 'Ágora', key: 'a' },
    { to: '/archivo', label: 'Archivo', key: 'h' },
    { to: '/megatendencias', label: 'Megatendencias', key: 'n' },
    { to: '/taller', label: 'Taller', key: 't' },
    { to: '/pronosticos', label: 'Pronósticos', key: 'f' },
  ],
  CEO: [
    { to: '/mando', label: 'Mando', key: 'c' },
    { to: '/simulador', label: 'Simulador', key: 's' },
    { to: '/brief', label: 'Brief ejecutivo', key: 'b' },
  ],
}

export const COMMON_NAV: Array<{ to: string; label: string }> = [
  { to: '/brief', label: 'Brief' },
  { to: '/dieta', label: 'Dieta' },
  { to: '/maquinas', label: 'Sala de máquinas' },
  { to: '/ayuda', label: 'Ayuda' },
]

/** Modo al que pertenece una ruta (para sincronizar el conmutador al navegar). */
export function modeForPath(path: string): Mode | null {
  for (const m of Object.keys(MODE_NAV) as Mode[]) {
    for (const item of MODE_NAV[m]) {
      if (item.to === '/' ? path === '/' : path === item.to || path.startsWith(`${item.to}/`)) return m
    }
  }
  if (path.startsWith('/eventos')) return 'ANALISTA'
  return null
}
