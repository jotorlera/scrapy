# TORNILLO SUELTO · frontend (motor ATLAS)

Interfaz de la terminal personal de inteligencia. React 19 + TypeScript estricto + Vite. Sin librerías de UI ni
CSS-in-JS: tokens CSS del kit Hespérides, CSS plano por componente y SVG propio para mapa, grafos y la gata.

## Desarrollo

```bash
# 1. API con datos reales (desde la raíz del repo)
ATLAS_SCHEDULER=0 .venv/bin/python -m uvicorn atlas_core.api.app:app --app-dir services/core --port 8765

# 2. Frontend con recarga en caliente (proxy de /api → 127.0.0.1:8765)
cd apps/web && npm install && npm run dev      # http://localhost:5173
```

Si la base está vacía, lanza «Ingestar ahora» en la Sala de máquinas (`/maquinas`) o `make ingest`. Los datos de
mercados se cargan con «Actualizar mercados» (`POST /api/machine/markets`).

## Construcción y producción

```bash
npm run build      # tsc -b + vite build → dist/
npm run preview    # sirve dist/ con el mismo proxy de /api
npm run lint       # oxlint
npm test           # vitest (jsdom): pruebas unitarias de src/**/*.test.ts
```

El backend sirve `apps/web/dist` como SPA (rutas de historial con fallback a `index.html`, `/assets` y `/fonts`).
Basta con arrancar la API sin Vite: `http://localhost:8765/`.

## Estructura

```
public/
  favicon.svg            tornillo torcido (icono de la pestaña)
  fonts/                 Noto Sans 300/400/600/700 + cursiva (copiadas de brand/fuentes)
src/
  main.tsx, App.tsx      arranque, enrutado (react-router, rutas de historial) y shell
  styles/
    tokens.css           paleta Hespérides, tema oscuro ([data-theme="dark"]), densidad ([data-density])
    base.css             @font-face, reset, tipografía, botones, tablas densas, foco visible, impresión
  api/
    types.ts             tipos derivados de las respuestas reales de la API
    client.ts            cliente fetch tipado (todas las rutas /api) y ApiError (409 = agentes sin clave)
    sse.ts               streaming de agentes: fetch con lector de stream para GET y POST (el cuerpo del 409/429
                         llega como evento `error`; sin EventSource no hay reconexión automática ni doble ejecución)
  state/store.tsx        contexto global: ajustes (GET/PUT /api/settings), modo, tema, densidad, selección,
                         panel contextual, estado de agentes, avisos; navegación por modo (MODE_NAV)
  lib/
    labels.ts            etiquetas en español de dominios, ecosistemas, bloques, niveles, estados, procedencia
    format.ts            fechas y cifras (es-ES), escala secuencial amarillo → negro (seqColor)
    hooks.ts             useAsync, useDietLog (POST /api/diet/log: open al abrir, read al ocultar/cerrar/desmontar),
                         useInterval, useSize…
    diet.ts              sesión de lectura de la DIETA (visibilitychange/pagehide, sendBeacon); con prueba unitaria
    keyboard.ts          atajos globales estilo gmail (g r, g e, j/k, o, n, f, ?, 1/2/3, ⌘K, [)
  components/
    ui/                  Card, Chip, StatusIcon, Level, ProvenanceChip, MaterialityBar + Breakdown (ⓘ),
                         DataTable, Sparkline, Tabs, EmptyState, ErrorBox, Modal, Popover, Markdown,
                         AgentStream, EventCard (+ EcosystemBar), QuoteHover
    shell/               Header (marca, modo, ⌘K, campana, brief, tema, ajustes), SideNav, ContextPanel
                         (documento con cita resaltada, salida de agentes, nota rápida → TALLER),
                         MarketTicker (cinta), CommandPalette, ShortcutsHelp
    map/WorldMap.tsx     mapa SVG con d3-geo (Natural Earth) y world-atlas 110m; país ↔ ISO2 por geoContains
    Tuerca.tsx           la gata: máquina de estados con tick de 100 ms, SVG y CSS propios
  screens/               una pantalla por ruta (ver tabla)
```

## Rutas

| Ruta | Pantalla | Datos |
|---|---|---|
| `/` | RADAR: mapa, deltas, top 15 | `GET /api/radar`, `/api/countries` |
| `/eventos`, `/eventos/:id` | lista filtrable y ficha con 8 pestañas y botones de agente | `/api/events`, `/api/events/{id}`, `/api/agents/*` |
| `/prisma`, `/prisma/:eventId` | matriz de cobertura, silencios, léxico, estatales, CSV | `/api/events/{id}/prism` |
| `/primarias` | flujo oficial, linajes y DIFF a dos columnas | `/api/primaries`, `/api/diff` |
| `/mercados` | cotizaciones por grupo, mercados de predicción, canales causales | `/api/markets` |
| `/paises`, `/paises/:iso2` | niveles A/B/C, ficha con variables, «¿Qué ha cambiado?», miniPRISMA | `/api/countries`, `/api/countries/{iso2}` |
| `/actores`, `/actores/:id` | buscador, menciones por día, co-menciones, afirmaciones atribuidas | `/api/actors` |
| `/agora`, `/agora/mapas/:id` | mapas argumentales (editor SVG), genealogía, lentes, tutor socrático | `/api/agora/*`, `/api/agents/lens|socratic` |
| `/archivo` | casos históricos, ficha, buscador de análogos con tabla de comparación | `/api/archive/*` |
| `/pronosticos`, `/pronosticos/:id` | preguntas, protocolo usuario-antes-que-sistema, mercado, resolución, calibración | `/api/forecasts/*` |
| `/taller` | notas con `[[enlaces]]`, retroenlaces, plantilla de ensayo, repaso espaciado | `/api/notes`, `/api/cards` |
| `/megatendencias` | estado honesto + señales estructurales | `/api/events` |
| `/mando` | negocios, alertas de exposición, radar regulatorio, diario de decisiones | `/api/mando` |
| `/simulador` | modo C «¿qué pasa si…?» | `POST /api/agents/what_if` |
| `/brief` | brief editorial (estudio / ejecutivo), historial, redactar, imprimir | `/api/brief/*` |
| `/dieta` | diversidad, entropías, puntos ciegos | `/api/diet/report` |
| `/maquinas` | totales, presupuesto, fuentes, jobs, coste LLM, acciones | `/api/machine/*` |
| `/ayuda` | atajos, niveles epistémicos, procedencia | — |

## Convenciones

- Español en UI, textos y comentarios; identificadores en inglés.
- Ningún dato inventado: cada cifra lleva fuente y hora; los errores explican qué falta y cómo resolverlo.
- Procedencia siempre visible (`title_source`, `extracted_by`, `composed_by`) y ⓘ con desglose en cada puntuación.
- Con `GET /api/agents/status` → `enabled: false` (o 409 en cualquier agente) los botones quedan deshabilitados con el
  mensaje de la API; el resto de la herramienta funciona sin clave.
- Capturas de verificación en `docs/capturas/` (claro y oscuro, 1440 px) generadas con Playwright.
