# 01 — Arquitectura

## 1. Decisión de formato (recomendación; confirmar o cambiar con un ADR)

**Aplicación web local-first + envoltorio nativo macOS con Tauri 2.**

- **Backend** en Python. El ecosistema de datos, NLP, OpenBB, Fundus y el Claude Agent SDK es Python.
- **Frontend** en React + TypeScript, servido en `http://localhost:5173` durante el desarrollo y como estáticos en producción.
- **App de Mac** (fase 6): Tauri 2 envuelve el frontend. Añade icono en la barra de menús con el Brief, notificaciones nativas para alertas de umbral alto, atajo global para la paleta de comandos y arranque automático de los servicios con docker compose u OrbStack.
- **Por qué no una app nativa pura (SwiftUI):** duplicaría el frontend, perdería el ecosistema de visualización web (deck.gl, MapLibre, globe.gl, Sigma.js, ECharts) y no aporta nada crítico.
- **Por qué no un HTML suelto:** la ingesta continua, los agentes, la base de datos histórica y las tareas programadas exigen servicios persistentes.
- **Evolución opcional (fase 7):** desplegar los servicios en un VPS pequeño (Hetzner u otro) para que la ingesta y el Brief de las 07:00 funcionen con el Mac apagado. El Mac y el móvil actúan como clientes, vía Tailscale.

## 2. Vista de capas

```
┌─────────────────────────────── PRESENTACIÓN ───────────────────────────────────┐
│ apps/web (React/TS/Vite) · apps/desktop (Tauri 2) · Brief por email/notificación│
├──────────────────────────────── API ───────────────────────────────────────────┤
│ services/core: FastAPI · REST + SSE (streaming de agentes) · WebSocket (radar)  │
│ Auth local (un usuario; token en llavero de macOS en la app Tauri)              │
├──────────────────────────────── AGENTES (runtime) ─────────────────────────────┤
│ Claude Agent SDK (Python): orquestador "editor-jefe" + subagentes especialistas │
│ Herramientas = servidores MCP internos + funciones Python registradas           │
├──────────────────────────────── MOTORES ───────────────────────────────────────┤
│ clustering · extracción de afirmaciones · verificación · marcos/narrativas ·    │
│ silencios · materialidad · transmisión a mercados · pronóstico · calibración ·  │
│ simulación · anti-burbuja · repaso espaciado                                    │
├──────────────────────────────── MODELO DEL MUNDO ──────────────────────────────┤
│ Postgres: entidades, afirmaciones, eventos, fuentes, actores, pronósticos,      │
│ variables de estado, aristas del grafo · pgvector: embeddings · DuckDB/Parquet: │
│ series temporales (macro, mercados, conflicto) · almacenamiento de artefactos   │
├──────────────────────────────── INGESTA ───────────────────────────────────────┤
│ services/workers: planificador (APScheduler/arq) · conectores por tipo de fuente│
│ RSS/Atom · extractor (Fundus → Trafilatura) · GDELT · ACLED · OpenBB · APIs     │
│ oficiales · mercados de predicción · Bluesky · X (opcional) · podcasts/vídeo    │
└────────────────────────────────────────────────────────────────────────────────┘
```

## 3. Stack detallado

### Backend (`services/core`, `services/workers`)
| Área | Elección | Notas |
|---|---|---|
| Lenguaje | Python 3.12, uv | |
| API | FastAPI + Pydantic v2 | OpenAPI → tipos TS generados con openapi-typescript |
| Colas y planificación | arq (Redis) + APScheduler | Colas separadas: `ingest`, `extract`, `analyze`, `agents`, `forecast` |
| DB | PostgreSQL 16 + pgvector + pg_trgm + full-text (`simple` + diccionarios por idioma) | Grafo como tablas `entity` y `edge`. Evaluar Apache AGE solo si las consultas recursivas lo piden (ADR) |
| Analítica | DuckDB sobre Parquet | Series macro, precios, ACLED; consultas rápidas desde la API |
| Extracción web | Fundus (medios soportados) → Trafilatura (resto) → readability como último recurso | Respetar robots.txt y las preferencias anti-IA de cada medio |
| Feeds | feedparser + autodescubrimiento de feeds (`<link rel="alternate">`, `/feed`, `/rss`, sitemaps de noticias) | |
| NLP | sentence-transformers (`BAAI/bge-m3`), HDBSCAN/BERTopic para clustering, spaCy/GLiNER para entidades, detección de idioma con fastText lid.176 o lingua | Enlazado de entidades a Wikidata (QID) |
| LLM | `anthropic` + `claude-agent-sdk` | Prompt caching obligatorio en prompts de sistema largos. Batch API para extracción masiva no urgente |
| Finanzas/macro | OpenBB Platform (+ `openbb-mcp-server`) | FRED, BCE, FMI, OCDE, yfinance, CBOE… según proveedor |
| Transcripción | faster-whisper (local) | Podcasts, ruedas de prensa, discursos |
| Diffs de documentos | difflib + normalización + diff semántico con LLM | Legislación, comunicados de bancos centrales |
| Observabilidad | structlog + OpenTelemetry → tabla `llm_call` y `job_run`, más un panel interno "SALA DE MÁQUINAS" | Coste por módulo y por día |

### Frontend (`apps/web`, `packages/ui`)
| Área | Elección |
|---|---|
| Base | React 19 + TypeScript strict + Vite |
| Estado y datos | TanStack Query + Zustand. SSE para el streaming de agentes |
| Estilo | Tailwind CSS v4 + componentes propios con primitives de Radix y la paleta de comandos `cmdk` |
| Mapas | MapLibre GL + deck.gl (capas: eventos, ACLED, rutas marítimas, choropleths) y globe.gl para la vista 3D |
| Grafos | Sigma.js (grafo grande de actores e ideas) + React Flow (mapas argumentales editables) |
| Gráficos | ECharts o visx. Sparklines propios. Evaluar Observable Plot para exploración |
| Tablas | TanStack Table con virtualización |
| Editor | TipTap (notas y ensayos en TALLER), con enlaces `[[entidad]]` |
| Tests | vitest + Playwright (e2e con capturas de cada pantalla) |

### Escritorio (`apps/desktop`)
Tauri 2 con plugins de notificación, atajo global, bandeja/menú, autoarranque y llavero. Si se decide empaquetar el backend dentro de la app, se hace con un sidecar (binario PyInstaller) y una alternativa a Docker (ADR). La opción por defecto es levantar los servicios con docker compose.

## 4. Flujo de datos principal

```
fuente → conector.fetch() → documento bruto (raw_document, hash, fecha, idioma)
      → extracción de texto limpio → deduplicación (hash + casi-duplicados por MinHash)
      → embeddings → asignación a evento (clustering incremental; ver docs/07)
      → extracción de entidades (con QID de Wikidata) y de afirmaciones (Haiku, "cite o descarta")
      → extracción de marcos (Entman: problema, causa, juicio moral, remedio) por artículo
      → actualización de variables de estado + puntuación de materialidad del evento
      → si materialidad ≥ umbral: los agentes analizan → afirmaciones verificadas contra primarias
        → generación de preguntas de pronóstico → motor de pronóstico
      → UI (RADAR/EVENTOS/PRISMA…) + alertas + Brief
```

## 5. Modelo del mundo
- **Entidades:** actor (persona u organización), país, institución, medio, autor, activo financiero, sector, concepto, obra filosófica, tratado, conflicto. Cada una con `wikidata_qid` si existe.
- **Aristas tipadas y fechadas:** `member_of`, `leads`, `funds`, `allied_with`, `sanctions`, `trades_with`, `cites`, `influenced_by`, `owns`, `exposed_to`, `opposes`, `votes_for`, `votes_against`… Todas con `valid_from`, `valid_to`, `source_id` y `confidence`.
- **Variables de estado** por país y sistema. Ver la taxonomía en `docs/07`: PODER, REGLAS, DINERO, FUERZA, LEGITIMIDAD, POSICIÓN EXTERIOR y ESTRUCTURA. Cada variable tiene una serie temporal y umbrales de cambio material.
- **Canales causales** (para la transmisión a mercados y los escenarios): grafo dirigido y editable (`petróleo↑ → inflación↑ → tipos↑ → valoración de crecimiento↓`) con elasticidades orientativas y fuente académica cuando exista.

## 6. Servidores MCP
**Internos**, expuestos a los agentes runtime y también a Claude Code durante el desarrollo:
- `atlas-news`: buscar eventos, artículos y cobertura por ecosistema.
- `atlas-claims`: consultar y registrar afirmaciones y su evidencia.
- `atlas-graph`: consultar entidades, relaciones y posiciones de actores.
- `atlas-state`: variables de estado y sus series.
- `atlas-forecast`: crear preguntas, registrar pronósticos y consultar tasas base y calibración.
- `atlas-primary`: buscar en documentos oficiales ingeridos y sus diffs.
- `atlas-library`: textos filosóficos, SEP, PhilPapers, notas del usuario.

**Externos:** `openbb-mcp` (mercados y macro). Opcionalmente, los que aporte cada proveedor.

Así un mismo motor sirve a la UI, a los agentes y a Claude Code.

## 7. Seguridad y privacidad (resumen; detalle en docs/12)
- Todo corre en local. La única salida es hacia fuentes públicas y hacia la API de Anthropic.
- `config/perfil.yaml` y los datos de negocio van en la DB local cifrada en reposo (FileVault) y nunca se envían completos al LLM: solo el contexto mínimo necesario para cada tarea.
- Secretos en `.env` o en el llavero de macOS.
- El contenido ingerido se trata como **no confiable**: nunca se ejecutan instrucciones que aparezcan dentro de artículos, tuits o PDF (defensa contra prompt injection). Los prompts runtime lo recuerdan explícitamente y la herramienta de escritura de los agentes tiene permisos mínimos.

## 8. Rendimiento objetivo
- RADAR carga en menos de 1,5 s con 30 días de datos.
- Búsqueda universal responde en menos de 500 ms (híbrida: BM25 + vector).
- De ingesta a evento visible: menos de 10 min en Tier 1 y menos de 60 min en el resto.
- Brief generado antes de las 07:00 hora local del usuario (Europe/Monaco por defecto; configurable).
