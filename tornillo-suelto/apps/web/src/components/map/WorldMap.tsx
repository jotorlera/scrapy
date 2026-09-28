/* Mapa mundial SVG con d3-geo (Natural Earth) y world-atlas 110m. Un punto por evento con geo; clic en país → ficha. */

import { geoContains, geoGraticule10, geoNaturalEarth1, geoPath, type GeoPermissibleObjects } from 'd3-geo'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { feature } from 'topojson-client'
import type { Topology, GeometryCollection } from 'topojson-specification'
import type { CountryRow, EventSummary } from '../../api/types'
import { hoursSince } from '../../lib/format'
import { domainColor, domainLabel } from '../../lib/labels'
import { useSize } from '../../lib/hooks'
import './map.css'

interface CountryFeature {
  type: 'Feature'
  id?: string | number
  properties: { name?: string }
  geometry: GeoPermissibleObjects & { type: string }
}

let topoCache: Promise<CountryFeature[]> | null = null
function loadCountries(): Promise<CountryFeature[]> {
  if (!topoCache) {
    topoCache = import('world-atlas/countries-110m.json').then((mod) => {
      const topo = (mod.default ?? mod) as unknown as Topology<{ countries: GeometryCollection }>
      const fc = feature(topo, topo.objects.countries) as unknown as { features: CountryFeature[] }
      return fc.features
    })
  }
  return topoCache
}

export interface WorldMapProps {
  events: EventSummary[]
  countries?: CountryRow[]
  onEvent?: (e: EventSummary) => void
  highlightIso2?: string | null
  minHeight?: number
}

export function WorldMap({ events, countries = [], onEvent, highlightIso2, minHeight = 360 }: WorldMapProps) {
  const [wrapRef, size] = useSize<HTMLDivElement>()
  const [features, setFeatures] = useState<CountryFeature[]>([])
  const [tip, setTip] = useState<{ x: number; y: number; title: string; sub: string } | null>(null)
  /* País con foco de teclado: su anillo se pinta aparte, encima de todos los países. */
  const [focusFeature, setFocusFeature] = useState<CountryFeature | null>(null)
  const nav = useNavigate()
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    let alive = true
    loadCountries().then((f) => alive && setFeatures(f))
    return () => {
      alive = false
    }
  }, [])

  const width = Math.max(320, size.width || 800)
  const height = Math.max(minHeight, Math.min(width * 0.52, size.height || minHeight))

  const projection = useMemo(() => geoNaturalEarth1().fitExtent([[4, 4], [width - 4, height - 4]], { type: 'Sphere' } as GeoPermissibleObjects), [width, height])
  const path = useMemo(() => geoPath(projection), [projection])

  /* País (iso2) de cada polígono: el punto del gazetteer (capital) que cae dentro de la geometría. */
  const featureIso = useMemo(() => {
    const map = new Map<CountryFeature, CountryRow>()
    if (!features.length || !countries.length) return map
    for (const c of countries) {
      const f = features.find((ft) => geoContains(ft as unknown as GeoPermissibleObjects, [c.lon, c.lat]))
      if (f && !map.has(f)) map.set(f, c)
    }
    return map
  }, [features, countries])

  const countryPaths = useMemo(() => features.map((f) => ({ f, d: path(f as unknown as GeoPermissibleObjects) ?? '' })), [features, path])
  const focusD = focusFeature ? path(focusFeature as unknown as GeoPermissibleObjects) : null
  const graticule = useMemo(() => path(geoGraticule10()) ?? '', [path])
  const sphere = useMemo(() => path({ type: 'Sphere' } as GeoPermissibleObjects) ?? '', [path])

  /* Puntos: tamaño por materialidad, color por dominio, halo si < 24 h. Los que comparten coordenadas se reparten en anillo. */
  const points = useMemo(() => {
    const now = Date.now()
    const groups = new Map<string, EventSummary[]>()
    for (const e of events) {
      if (!e.geo) continue
      const key = `${e.geo.lat.toFixed(2)},${e.geo.lon.toFixed(2)}`
      const g = groups.get(key) ?? []
      g.push(e)
      groups.set(key, g)
    }
    const out: Array<{ e: EventSummary; x: number; y: number; r: number; fresh: boolean }> = []
    for (const g of groups.values()) {
      g.sort((a, b) => (b.materiality ?? 0) - (a.materiality ?? 0))
      const p = projection([g[0].geo!.lon, g[0].geo!.lat])
      if (!p) continue
      g.forEach((e, i) => {
        const r = 2.2 + Math.sqrt(Math.max(0, e.materiality ?? 0)) * 0.85
        let x = p[0]
        let y = p[1]
        if (i > 0) {
          const ring = Math.ceil(i / 6)
          const angle = ((i - 1) % 6) * (Math.PI / 3) + ring * 0.5
          x += Math.cos(angle) * (7 + ring * 6)
          y += Math.sin(angle) * (7 + ring * 6)
        }
        out.push({ e, x, y, r, fresh: (hoursSince(e.first_seen_at, now) ?? 99) < 24 })
      })
    }
    return out.sort((a, b) => b.r - a.r)
  }, [events, projection])

  const showTip = (evt: React.MouseEvent, title: string, sub: string) => {
    const rect = wrapRef.current?.getBoundingClientRect()
    if (!rect) return
    setTip({ x: evt.clientX - rect.left + 12, y: evt.clientY - rect.top + 12, title, sub })
  }

  return (
    <div className="worldmap" ref={wrapRef} style={{ minHeight }}>
      <svg ref={svgRef} width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Mapa mundial de eventos">
        <path d={sphere} className="sphere" />
        <path d={graticule} className="graticule" />
        <g className="countries">
          {countryPaths.map(({ f, d }, i) => {
            const c = featureIso.get(f)
            const iso = c?.iso2
            return (
              <path
                key={String(f.id ?? i)}
                d={d}
                className={`country ${iso ? 'has-sheet' : ''} ${iso && iso === highlightIso2 ? 'hl' : ''}`}
                tabIndex={iso ? 0 : undefined}
                role={iso ? 'link' : undefined}
                aria-label={iso ? `Ficha de ${c!.name}` : undefined}
                onClick={iso ? () => nav(`/paises/${iso}`) : undefined}
                onKeyDown={iso ? (e) => e.key === 'Enter' && nav(`/paises/${iso}`) : undefined}
                onFocus={
                  iso
                    ? (e) => {
                        if (e.currentTarget.matches(':focus-visible')) setFocusFeature(f)
                      }
                    : undefined
                }
                onBlur={iso ? () => setFocusFeature(null) : undefined}
                onMouseMove={(e) => showTip(e, c?.name ?? f.properties.name ?? '—', iso ? `${iso} · nivel ${c!.level} · ${c!.events_7d} eventos 7 d` : 'sin ficha en el gazetteer')}
                onMouseLeave={() => setTip(null)}
              />
            )
          })}
        </g>
        {focusD && (
          <g className="country-focus" aria-hidden="true">
            <path d={focusD} className="ring outer" />
            <path d={focusD} className="ring inner" />
          </g>
        )}
        <g className="events">
          {points.map(({ e, x, y, r, fresh }) => (
            <g key={e.id} transform={`translate(${x.toFixed(1)},${y.toFixed(1)})`}>
              {fresh && <circle r={r + 3.5} className="halo" />}
              <circle
                r={r}
                className="ev"
                style={{ fill: domainColor(e.domain) }}
                tabIndex={0}
                role="link"
                aria-label={e.title_neutral}
                onClick={(ev) => {
                  ev.stopPropagation()
                  if (onEvent) onEvent(e)
                  else nav(`/eventos/${e.id}`)
                }}
                onKeyDown={(ev) => ev.key === 'Enter' && (onEvent ? onEvent(e) : nav(`/eventos/${e.id}`))}
                onMouseMove={(ev) => {
                  ev.stopPropagation()
                  showTip(ev, e.title_neutral, `${domainLabel(e.domain)} · materialidad ${(e.materiality ?? 0).toFixed(0)} · ${e.countries.join(' ')} · ${e.n_sources} fuentes${fresh ? ' · nuevo (< 24 h)' : ''}`)
                }}
                onMouseLeave={() => setTip(null)}
              />
            </g>
          ))}
        </g>
      </svg>
      {tip && (
        <div className="map-tip" style={{ left: Math.min(tip.x, width - 260), top: tip.y }} role="tooltip">
          <div className="t">{tip.title}</div>
          <div className="s">{tip.sub}</div>
        </div>
      )}
      <div className="map-legend" aria-hidden="true">
        {['politics', 'economy', 'conflict', 'society', 'technology', 'health', 'environment', 'law'].map((d) => (
          <span key={d}>
            <i style={{ background: domainColor(d) }} /> {domainLabel(d)}
          </span>
        ))}
        <span>
          <i className="halo-legend" /> &lt; 24 h
        </span>
        <span className="muted">tamaño = materialidad</span>
      </div>
    </div>
  )
}
