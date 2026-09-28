import { Suspense, lazy, useEffect, useMemo } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { CommandPalette } from './components/shell/CommandPalette'
import { ContextPanel } from './components/shell/ContextPanel'
import { Header } from './components/shell/Header'
import { MarketTicker } from './components/shell/MarketTicker'
import { ShortcutsHelp } from './components/shell/ShortcutsHelp'
import './components/shell/shell.css'
import { Tuerca } from './components/Tuerca'
import { Loading } from './components/ui/basics'
import { useGlobalShortcuts } from './lib/keyboard'
import { modeForPath, StoreProvider, useStore } from './state/store'
import { SideNav } from './components/shell/SideNav'

const Radar = lazy(() => import('./screens/Radar'))
const EventsList = lazy(() => import('./screens/EventsList'))
const EventDetail = lazy(() => import('./screens/EventDetail'))
const Prism = lazy(() => import('./screens/Prism'))
const Primaries = lazy(() => import('./screens/Primaries'))
const Markets = lazy(() => import('./screens/Markets'))
const Countries = lazy(() => import('./screens/Countries'))
const CountryDetail = lazy(() => import('./screens/CountryDetail'))
const Actors = lazy(() => import('./screens/Actors'))
const Agora = lazy(() => import('./screens/Agora'))
const MapEditor = lazy(() => import('./screens/MapEditor'))
const Archive = lazy(() => import('./screens/Archive'))
const Forecasts = lazy(() => import('./screens/Forecasts'))
const Taller = lazy(() => import('./screens/Taller'))
const Megatrends = lazy(() => import('./screens/Megatrends'))
const Mando = lazy(() => import('./screens/Mando'))
const Simulator = lazy(() => import('./screens/Simulator'))
const Brief = lazy(() => import('./screens/Brief'))
const Diet = lazy(() => import('./screens/Diet'))
const Machine = lazy(() => import('./screens/Machine'))
const Help = lazy(() => import('./screens/Help'))

function Toasts() {
  const { toasts } = useStore()
  if (!toasts.length) return null
  return (
    <div className="toasts" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.kind}`}>
          {t.msg}
        </div>
      ))}
    </div>
  )
}

function NotFound() {
  return (
    <div>
      <h1>Ruta no encontrada</h1>
      <p className="muted">Prueba con «g r» para volver al Radar o ⌘K para buscar.</p>
    </div>
  )
}

function Shell() {
  const { setPaletteOpen, setHelpOpen, setMode, mode, setPanelOpen, panelOpen, paletteOpen, helpOpen } = useStore()
  const loc = useLocation()

  // Sincroniza el conmutador de modo con la ruta
  useEffect(() => {
    const m = modeForPath(loc.pathname)
    if (m && m !== mode) setMode(m)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loc.pathname])

  const handlers = useMemo(
    () => ({
      openPalette: () => setPaletteOpen(true),
      openHelp: () => setHelpOpen(true),
      setMode,
      togglePanel: () => setPanelOpen(!panelOpen),
      anyModalOpen: () => paletteOpen || helpOpen || !!document.querySelector('.modal-backdrop'),
    }),
    [setPaletteOpen, setHelpOpen, setMode, setPanelOpen, panelOpen, paletteOpen, helpOpen],
  )
  useGlobalShortcuts(handlers)

  const flush = loc.pathname === '/'
  return (
    <div className="shell">
      <Header />
      <SideNav />
      <main className={`main ${flush ? 'flush' : ''}`} id="main">
        <Suspense fallback={<Loading text="Cargando pantalla…" />}>
          <Routes>
            <Route path="/" element={<Radar />} />
            <Route path="/eventos" element={<EventsList />} />
            <Route path="/eventos/:id" element={<EventDetail />} />
            <Route path="/prisma" element={<Prism />} />
            <Route path="/prisma/:eventId" element={<Prism />} />
            <Route path="/primarias" element={<Primaries />} />
            <Route path="/mercados" element={<Markets />} />
            <Route path="/paises" element={<Countries />} />
            <Route path="/paises/:iso2" element={<CountryDetail />} />
            <Route path="/actores" element={<Actors />} />
            <Route path="/actores/:id" element={<Actors />} />
            <Route path="/agora" element={<Agora />} />
            <Route path="/agora/mapas/:id" element={<MapEditor />} />
            <Route path="/archivo" element={<Archive />} />
            <Route path="/pronosticos" element={<Forecasts />} />
            <Route path="/pronosticos/:id" element={<Forecasts />} />
            <Route path="/taller" element={<Taller />} />
            <Route path="/megatendencias" element={<Megatrends />} />
            <Route path="/mando" element={<Mando />} />
            <Route path="/simulador" element={<Simulator />} />
            <Route path="/brief" element={<Brief />} />
            <Route path="/dieta" element={<Diet />} />
            <Route path="/maquinas" element={<Machine />} />
            <Route path="/ayuda" element={<Help />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </main>
      <ContextPanel />
      <MarketTicker />
      <CommandPalette />
      <ShortcutsHelp />
      <Toasts />
      <Tuerca />
    </div>
  )
}

export default function App() {
  return (
    <StoreProvider>
      <Shell />
    </StoreProvider>
  )
}
