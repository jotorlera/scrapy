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

### Frontend
- Ver `apps/web/README.md` (construido por el agente frontend; estilo Hespérides, gata Tuerca, 18 rutas).

## Cómo verlo
```
make install && make seed && make up      # http://127.0.0.1:8765  (API: /api/docs)
make ingest                                # fuerza una pasada
make test                                  # 30 tests
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
  hay series macro ni de conflicto (conectores pendientes; el `.env.example` los prevé).
- **Marcos (Entman)**: tabla y prompt listos; el clasificador de marcos no se ejecuta sin clave.
- **Fuentes**: 199/301 con feed. Sin feed (AP, AFP, Reuters, Bloomberg, EUR-Lex, Consilium, FMI, OCDE, EMA, FDA,
  Congreso, BdE, INE…) requieren API o scraping específico (siguiente iteración: `sitemap_news` y conectores
  `eurlex`/`boe` API).
- **Sin ACLED, GDELT (429 sin clave), OpenSanctions, ParlaMint, OpenAlex**: pendientes.
- **SIMULADOR**: solo modo C (requiere clave). Modos A y B fuera de alcance.
- **MEGATENDENCIAS**: sin conectores de datos estructurales; pantalla honesta con señales de temas.
- **Traducción bajo demanda**: no implementada (requiere clave; los documentos se guardan en su idioma).
- **Tests e2e de UI**: script de capturas (`scripts/screenshots.py`) listo; depende del frontend compilado.
- No hay autenticación: la API escucha solo en 127.0.0.1 (uso personal).

## Siguiente
1. Probar la mesa de agentes con clave real y ajustar prompts (extractor, títulos, brief) midiendo coste.
2. Conector `sitemap_news` y APIs de EUR-Lex/BOE/congress.gov para ampliar primarias.
3. bge-m3 opcional medido en el Mac; conjunto dorado de 25 eventos para pureza/fragmentación.
4. FRED (con clave) → variables MONEY reales; ACLED (con cuenta) → FORCE.
5. Empaquetado Tauri (fase 6) cuando la web esté estable.
