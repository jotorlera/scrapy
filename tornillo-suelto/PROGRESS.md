# PROGRESS — TORNILLO SUELTO · motor ATLAS

Actualizado: 2026-09-28 (sesión de construcción inicial, en la nube).

## Hecho

### Fase 0 — Fundaciones (completa)
- Planteamiento pulido (`docs/PLANTEAMIENTO.md`) y 6 ADR (`docs/adr/`): SQLite local-first, web local sin Tauri,
  mapa SVG + embeddings locales por niveles, modo sin clave con etiquetado de procedencia, datos de mercado sin
  OpenBB, nombre/estilo/gata.
- Monorepo: `services/core/atlas_core` (FastAPI), `apps/web` (React + TS + Vite), `config/`, `prompts/runtime/`,
  `tests/`, `Makefile`, `.env.example`, `.gitignore`.
- Esquema SQLite (FTS5) fiel al `schema.sql` de referencia; registro de `llm_call` y `job_run` desde el primer día.
- CLI `atlas` (seed, ingest, markets, recompute, brief, serve, stats, verify-feeds).

### Fase 1 — Ingesta y RADAR (completa, sin LLM)
- Conector RSS/Atom con ETag/If-Modified-Since, reintento con UA de navegador y autodescubrimiento de feeds.
- **199 feeds verificados** de las 301 fuentes semilla (`config/feeds.yaml`, `scripts/verify_feeds.py`).
- Pipeline: documentos → deduplicación → embeddings (hashing con IDF del corpus + tokens de entidad) → gazetteer
  (≈140 países, ≈60 instituciones/empresas, 16 temas, alias en 6 idiomas) → clustering incremental con regla de
  misma fuente → consolidación periódica → afirmaciones con cita (heurístico, «cita o descarta») → cobertura e
  índice de silencio → materialidad con desglose → deltas de estado → exposición (MANDO).
- Ingesta real medida: 120 fuentes → 3.812 documentos en 110 s; eventos multi-fuente coherentes (dimisión de
  Vučić en 8 medios, referéndum suizo de neutralidad, detenciones en RAF Fairford, tiroteos en Sudáfrica…).
- Planificador verificado con la API levantada: mercados cada 15 min, ingesta de las 199 fuentes en dos pasadas
  (6.252 documentos, 106 eventos multi-fuente, 15.722 afirmaciones con cita), ETag/If-Modified-Since operativo
  (32 fuentes «no modificadas» en la segunda pasada) y la API respondiendo en < 0,3 s durante el procesado (el
  trabajo pesado corre fuera del bucle de eventos).
- Cinta de mercados (Yahoo chart API) y mercados de predicción (Polymarket, Manifold) con hora y fuente del dato.

### Fase 2 — Rigor (parcial)
- PRISMA completo: matriz ideología × bloque, índice de silencio (Poisson estandarizado con cuotas a 30 días,
  test sintético en `tests/`), léxico diferencial (Monroe et al. 2008), medios estatales marcados.
- PRIMARIAS: flujo oficial de 40+ instituciones y DIFF frase a frase con cambios materiales.
- Estados de afirmación con regla determinista (primaria o ≥ 2 fuentes independientes; misma cita = misma
  agencia) y `claim_revision` en cada cambio.
- BRIEF por reglas con cuotas, divergencia narrativa, primaria, por qué importa y concepto del grado.
- Mesa de agentes implementada (extractor, títulos neutros, editor/dossier, explícamelo en 60 s, lentes, tutor
  socrático, ¿qué ha cambiado?, traductor normativo, equipo rojo, modo C, ensemble de pronóstico, redacción del
  brief) sobre la API de Anthropic con salida validada, caché de prompts, presupuesto y registro. **No probada con
  clave** (no hay `ANTHROPIC_API_KEY` en el entorno de construcción).

### Fase 4/5/6 — piezas adelantadas
- PRONÓSTICOS: ciclo completo (crear con filtro de calidad → usuario antes que sistema → enlazar mercado →
  resolver → Brier/log score → calibración con Wilson y Murphy). 6 plantillas recurrentes sembradas.
- ÁGORA: mapa argumental de la RBU (14 nodos con autores, obras y evidencia empírica), análisis de premisas sin
  apoyo/objeciones sin respuesta/ciclos, genealogía de la libertad (15 autores).
- ARCHIVO: 81 casos históricos codificados con variables y fuentes, análogos por similitud, tabla comparativa.
- TALLER: notas con `[[enlaces]]`, retroenlaces, exportación Markdown, repaso espaciado (FSRS-lite).
- MANDO: negocios del perfil, exposición por canal con reglas conservadoras, radar regulatorio, diario de
  decisiones con pre-mortem.
- DIETA: entropía normalizada por 4 ejes y puntos ciegos sobre el registro local de lectura.
- SALA DE MÁQUINAS: salud por fuente, jobs, coste LLM por día/módulo/modelo, presupuesto, disparadores.

### Frontend (`apps/web`, React 19 + TypeScript + Vite)
- Sistema de diseño Hespérides en `src/styles/tokens.css`: amarillo #FFD100 como único acento, blanco/negro,
  esquinas rectas, sin sombras ni degradados, filetes amarillos, Noto Sans local (300/400/600/700), cifras en
  monoespaciada tabular; tema claro por defecto y oscuro completo; densidad compacta/cómoda.
- Shell: modos ANALISTA/PENSADOR/CEO, navegación por modo, paleta ⌘K (búsqueda + acciones), atajos estilo gmail
  (`g r/e/p/i/m/g/o/a/h/t/f/c/s/b/d/x`, `j/k`, `o`, `n`, `f`, `?`, `1/2/3`), panel contextual plegable con
  streaming de agentes y nota rápida, cinta de mercados con sparklines, campana de alertas, ajustes persistidos.
- 24 rutas (18 pantallas) con datos reales: Radar (mapa SVG d3-geo), Eventos (8 pestañas, botones de agente con estado sin
  clave), Prisma (matriz, silencios, léxico, CSV), Primarias (+DIFF), Mercados (cinta, predicción, grafo de
  canales), Países, Actores, Ágora (editor de mapas argumentales con análisis, genealogía, lentes, tutor),
  Archivo, Pronósticos (protocolo «tu probabilidad antes que la del sistema», calibración con Wilson), Taller
  (notas con `[[enlaces]]`, repaso), Megatendencias (estado honesto), Mando, Simulador (modo C), Brief
  (editorial, imprimible), Dieta, Sala de máquinas, Ayuda.
- **Tuerca** (`src/components/Tuerca.tsx`): gata negra con collar amarillo en SVG propio; sigue al cursor, se
  sienta, se lame, se duerme sobre la cinta, persigue un tornillo, ronronea, se aparta de los formularios, se
  desactiva por ajuste y por `prefers-reduced-motion`.
- Verificación: `npm run build` sin errores de TypeScript. `make screenshots` (`scripts/screenshots.py`) recorre 16
  de las 24 rutas en claro y oscuro solo a 1440 px (docs/spec/09 pedía también 1920) y escribe
  `{ruta}-{tema}-1440.png`; no cubre `/megatendencias`, `/simulador`, `/ayuda` ni las fichas con ID. Las capturas
  de `docs/capturas/` (`radar_light.png`, fichas de evento/actor/pronóstico, genealogía de Ágora, Tuerca) se
  tomaron a mano y el script no las regenera con esos nombres. La ausencia de errores de consola y de peticiones
  fallidas se comprobó a mano, no está automatizada (el script solo hace `goto` + captura).
- Detalle de arquitectura y carpetas en `apps/web/README.md`.

## Cómo verlo
```
make install && make seed && make up      # http://127.0.0.1:8765  (API: /api/docs)
make ingest                                # fuerza una pasada
make test                                  # pytest: motores, API, pipeline, conectores, planificador, agentes, privacidad
```

## Decisiones
ADR-0001 … ADR-0006 en `docs/adr/`. Cambios respecto a la especificación: SQLite en vez de Postgres/Redis; sin
Tauri ni OpenBB en esta entrega; embeddings por hashing con IDF por defecto (bge-m3 opcional); los motores
deterministas son el núcleo y el LLM es una capa opcional etiquetada.

## Deuda técnica y límites conocidos (sin adornos)
- **Clustering multilingüe limitado** con el embedder por defecto: la misma noticia en inglés y francés suele
  quedar en dos eventos (los tokens de entidad ayudan, pero no bastan). Con `ATLAS_EMBEDDINGS=bge-m3` mejora;
  no se ha podido medir aquí (descarga de 2,3 GB).
- **Afirmaciones heurísticas**: son frases literales del titular/entradilla, no afirmaciones atómicas. El extractor
  Haiku está implementado pero sin probar con clave. La tasa de «confirmadas» es baja por diseño.
- **Títulos de evento** = titular del documento principal (etiquetado). El título neutro requiere clave.
- **Variables de estado**: solo deltas categóricos desde eventos y `fx_vs_usd` desde la cinta. Sin FRED/ACLED no
  hay series macro ni de conflicto: conectores pendientes. `FRED_API_KEY` está reservada en `settings.py` y
  comentada en `.env.example`, pero ningún código la lee todavía; ADR-0005 lo recoge. Metaculus tampoco está
  implementado (solo Polymarket y Manifold).
- **Marcos (Entman)**: clasificador **no implementado**. Solo existen la tabla `frame` y el prompt
  `prompts/runtime/clasificador_marcos.md`; ningún job, endpoint ni agente lo invoca, así que
  `GET /api/events/{id}/prism` devuelve `frames: []` con y sin clave (la UI de PRISMA muestra una nota). Pendiente
  (ver «Siguiente»).
- **Prompts sin agente cableado (8/16)**: analista_conflicto, analista_discurso, auditor_evidencia,
  clasificador_marcos, estratega_corporativo, estratega_mercados, historiador, macroeconomista. La mesa real es
  extractor, editor_jefe, analista_regional, filosofo, tutor_socratico, equipo_rojo, superpronosticador
  (`tests/test_extra_prompts.py` lo comprueba). Las ocho mejoras «con clave» que `docs/PLANTEAMIENTO.md` §3 marca
  como pendientes (marcos, resumen del diff, debate alcista/bajista, posiciones de actores, similitudes de
  ARCHIVO, tarjetas de TALLER, valoración de exposición, steelman de DIETA) no tienen endpoint.
- **Perfil personal**: `config/perfil.yaml` se versionó por error en el commit inicial (6b44d95) de la rama
  `claude/cloud-tool-cat-feature-dtnbrj` en un repositorio público. Ya está en `.gitignore` y fuera del índice,
  con plantilla `config/perfil.example.yaml` y guardarraíl `tests/test_extra_privacy.py`; el historial remoto
  sigue conteniéndolo (ver «Siguiente», punto 1).
- **Fuentes**: 199/301 con feed. Sin feed (AP, AFP, Reuters, Bloomberg, EUR-Lex, Consilium, FMI, OCDE, EMA, FDA,
  Congreso, BdE, INE…) requieren API o scraping específico (siguiente iteración: `sitemap_news` y conectores
  `eurlex`/`boe` API).
- **Sin ACLED, GDELT (429 sin clave), OpenSanctions, ParlaMint, OpenAlex**: pendientes.
- **SIMULADOR**: solo modo C (requiere clave). Modos A y B fuera de alcance.
- **MEGATENDENCIAS**: sin conectores de datos estructurales; pantalla honesta con señales de temas.
- **Traducción bajo demanda**: no implementada (requiere clave; los documentos se guardan en su idioma).
- **Tests e2e de UI**: solo recorrido con capturas (sin aserciones); sin objetivo móvil (la rejilla colapsa a una
  columna por debajo de 1000 px).
- No hay autenticación: la API escucha solo en 127.0.0.1 (uso personal).

## Siguiente
1. **Privacidad del perfil (urgente, fuera del código):** tratar `config/perfil.yaml` como divulgado. Reescribir
   el historial (`git filter-repo --path tornillo-suelto/config/perfil.yaml --invert-paths`), `git push --force`
   de la rama y borrar cualquier rama remota que aún contenga 6b44d95; después pedir a GitHub Support la purga de
   vistas cacheadas y la recolección de basura en la red de forks («Removing sensitive data from a repository»,
   indicando SHA y ruta), porque los commits colgantes siguen accesibles por SHA. Valorar repo privado o sacar
   TORNILLO SUELTO a un repositorio propio no forkeado.
2. Clasificador de marcos (Entman): agente `bulk` con `clasificador_marcos`, escritura en `frame`/`document_frame`
   y retirar la nota de PRISMA. Hasta entonces, `frames: []`.
3. Probar la mesa de agentes con clave real y ajustar prompts (extractor, títulos, brief) midiendo coste; cablear
   (o retirar) los 8 prompts sin agente y actualizar `docs/PLANTEAMIENTO.md` §3 y `tests/test_extra_prompts.py`.
4. `scripts/screenshots.py`: nombres `{ruta}_{tema}.png` como en `docs/capturas/`, rutas que faltan
   (`/megatendencias`, `/simulador`, `/ayuda`, fichas con IDs reales de la API), aserción de errores de consola y
   peticiones fallidas (exit 1) y `--widths 1440,1920` en el `Makefile`.
5. Conector `sitemap_news` y APIs de EUR-Lex/BOE/congress.gov para ampliar primarias.
6. bge-m3 opcional medido en el Mac; conjunto dorado de 25 eventos para pureza/fragmentación.
7. FRED (con clave; `connectors/fred.py`, hoy inexistente) → variables MONEY reales; ACLED (con cuenta) → FORCE.
8. Empaquetado Tauri (fase 6) cuando la web esté estable.
