# 03 — Fuentes y datos

La selección y clasificación de fuentes es **el corazón del producto**. Un modelo excelente con fuentes mal clasificadas produce análisis sesgado con apariencia de rigor.

## 1. Taxonomía de fuentes (cada fuente tiene todos estos campos)

| Campo | Valores |
|---|---|
| `type` | `wire` (agencia), `newspaper`, `broadcaster`, `digital_native`, `magazine`, `state_media`, `think_tank`, `institution` (gobierno, parlamento, organismo), `central_bank`, `court`, `statistical_office`, `intl_org`, `academic`, `newsletter` (Substack…), `podcast`, `social_account`, `data_api` |
| `tier` | 1 = fuente primaria o dato oficial; 2 = agencia o medio de referencia con estándares de corrección; 3 = medio de opinión o partidista con información útil; 4 = baja fiabilidad (solo para análisis de narrativas, nunca como fuente de hechos) |
| `country`, `languages` | ISO 3166 / ISO 639 |
| `region_bloc` | anglo, eu, es, latam, arab, turkey, russia, china, india, japan_korea, africa, other_asia, oceania, global |
| `state_relation` | `independent`, `public_service_independent` (BBC, RTVE…), `state_aligned`, `state_controlled` |
| `ownership` | texto libre + entidad en el grafo (propietario) |
| `ideology` | vector multidimensional (ver abajo) + `ideology_label` humano + `ideology_confidence` (0-1) + `ideology_provenance` (qué fuentes justifican la etiqueta: estudios académicos, Media Bias/Fact Check, AllSides, Ground News, Reuters Institute Digital News Report, criterio editorial propio) |
| `factual_record` | `high`, `mixed`, `low`, `unknown` + procedencia |
| `corrections_policy` | `yes`, `no`, `unknown` + URL |
| `paywall` | `none`, `metered`, `hard` |
| `access` | `rss`, `sitemap`, `api`, `scrape_allowed`, `metadata_only` |
| `ai_optout` | booleano (robots.txt / TDM reservation). Si es true, se usan solo metadatos y titular |
| `review_status` | `seed_unverified`, `verified`, `disputed` |

**Vector ideológico** (escala -1 a +1, con `null` si no aplica):
- `econ`: intervencionista ↔ libre mercado
- `social`: progresista ↔ conservador
- `authority`: libertario ↔ autoritario
- `nation`: cosmopolita/supranacional ↔ nacional/soberanista
- `establishment`: antisistema ↔ institucional
- `foreign_policy`: liberal-internacionalista ↔ realista/restriccionista

> Las etiquetas izquierda/derecha son **relativas a cada país**. Lo que es "centro" en EE. UU. no lo es en Suecia. Por eso el vector se complementa con `ideology_label_local` y la UI de PRISMA permite agrupar por ecosistema local o global.

**Clasificar también a nivel de artículo y autor.** La etiqueta del medio es solo un previo. Cada artículo recibe `frame_ids` y una posición estimada **en el tema concreto**, y cada autor acumula su propio perfil con el tiempo.

## 2. Semilla de fuentes
`config/fuentes.seed.yaml` contiene unas 300 fuentes mundiales con clasificación inicial `seed_unverified`. **Tarea de la fase 1 (agente `curador-fuentes`):**
1. Autodescubrir los feeds (RSS, Atom, sitemaps de noticias) de cada dominio.
2. Verificar `access`, `paywall` y `ai_optout` leyendo robots.txt y los términos.
3. Contrastar la clasificación ideológica con al menos 2 fuentes de rating y justificar en `ideology_provenance`. Si hay desacuerdo, `review_status: disputed`, visible en la UI.
4. Ampliar hasta unas 1.500 fuentes en la fase 3 usando el directorio de Media Cloud (colecciones por país) como base.

## 3. Conectores por tipo (interfaz `SourceConnector`)

| Conector | Qué trae | Frecuencia | Notas |
|---|---|---|---|
| `rss` | Artículos de medios con feed | 5-15 min (Tier 1-2), 60 min (resto) | ETag/If-Modified-Since |
| `sitemap_news` | Artículos vía sitemap de Google News | 15 min | Para medios sin RSS |
| `fundus` | Texto limpio de los medios soportados | tras `rss`/`sitemap` | Mayor calidad de extracción |
| `trafilatura` | Texto limpio genérico | como respaldo | |
| `gdelt` | Eventos, GKG (temas, tonos, entidades), API DOC | 15 min | Cobertura mundial de los países de vigilancia |
| `mediacloud` | Búsqueda en su archivo y directorio | bajo demanda y diario | Requiere cuenta; uso académico |
| `acled` | Eventos de conflicto y protesta + CAST | diario/semanal | Cuenta gratuita; atribución obligatoria |
| `openbb` | Macro, mercados, divisas, materias primas, tipos | según serie (tick diario para la mayoría) | Vía Python SDK o `openbb-mcp` |
| `prediction_markets` | Polymarket (API Gamma pública), Kalshi (API pública), Manifold, Metaculus (API) | 15-60 min | Solo lectura. Nunca se opera |
| `eurlex` | Legislación UE (CELLAR/SPARQL, búsqueda) | diario | Borradores y actos adoptados |
| `boe` | BOE (API de datos abiertos) | diario | |
| `congreso_es`, `senado_es` | Iniciativas, votaciones, diarios de sesiones | diario | Datos abiertos |
| `europarl` | Votaciones, textos, debates (API de datos abiertos) | diario | |
| `uscongress` | congress.gov API | diario | Clave gratuita |
| `un` | UN Digital Library, votaciones AGNU, Consejo de Seguridad | diario | |
| `central_banks` | Comunicados, actas, discursos (Fed, BCE, BoE, BoJ, BdE, CBRT…) | horaria en días de reunión | Diff automático |
| `courts` | TJUE (CURIA), TEDH (HUDOC), TC, Supremo EE. UU. | diario | |
| `stats` | Eurostat, INE, BLS, BEA, ONS, TÜİK… (vía OpenBB o directo) | según calendario | |
| `parlamint` | Corpus histórico de debates (ParlaMint/ParlaCAP) | una vez + actualizaciones | Para ACTORES y entrenamiento |
| `openalex` | Papers, autores, citas | diario por tema | Gratuito |
| `semantic_scholar` | Papers y resúmenes | bajo demanda | Clave gratuita |
| `philpapers`, `sep` | Metadatos y enlaces | bajo demanda | Enlazar, no reproducir |
| `gutenberg`, `perseus`, `wikisource` | Textos de dominio público | una vez | Canon de ÁGORA |
| `wikidata` | Identidades de entidades, relaciones | bajo demanda + caché | Resolución de entidades |
| `opensanctions` | Sanciones, personas políticamente expuestas | diario | Revisar licencia (uso no comercial gratuito) |
| `vdem`, `manifesto`, `parlgov`, `sipri`, `ucdp`, `cow` | Datasets estructurales | trimestral/anual | Revisar licencias |
| `bluesky` | Cuentas de las listas epistemológicas (AT Protocol / Jetstream) | tiempo real | Abierto |
| `x` | Cuentas de las listas | según presupuesto | Opcional, de pago. Desactivado por defecto |
| `substack`, `newsletters` | RSS | 60 min | |
| `podcasts` | RSS + transcripción faster-whisper | diario | Solo episodios de fuentes seleccionadas |
| `youtube` | Transcripciones de canales oficiales (ruedas de prensa) | diario | Respetar términos |
| `clinical_trials` | ClinicalTrials.gov, EU CTR | diario | Para MANDO (sector salud) |

## 4. Idiomas
- Detección automática; el original se guarda siempre.
- Traducción al español bajo demanda (Haiku), cacheada. En la UI el original está a un clic.
- Embeddings multilingües (bge-m3), de modo que el clustering agrupa artículos del mismo evento en distintos idiomas.
- Idiomas prioritarios de la fase 1: es, en, fr, de, it, pt, ar, tr, ru, zh, ja. Fase 3: fa, he, hi, ko, uk, pl, id, sw.

## 5. Niveles de atención por país
Definidos en `config/paises.yaml`:
- **Nivel A (profundidad):** ficha completa, primarias vigiladas, PRISMA local y deltas diarios.
- **Nivel B (seguimiento):** ficha estándar, agencias y 2-4 medios nacionales.
- **Nivel C (vigilancia):** GDELT + ACLED + agencias internacionales. Solo alertas de materialidad alta.

## 6. Reglas de ingesta
- Respetar robots.txt, los límites de velocidad (un User-Agent identificable con contacto) y las preferencias TDM y anti-IA.
- Para los medios de pago: titular, entradilla, metadatos y enlace. El texto completo solo si el usuario tiene suscripción y la configura explícitamente, y siempre para uso privado.
- Deduplicación: hash exacto + MinHash/SimHash para las reediciones de agencias.
- Cada documento guarda: `url`, `canonical_url`, `source_id`, `published_at`, `fetched_at`, `lang`, `title`, `text`, `authors`, `hash`, `extraction_method` y `paywalled`.
- **Todo contenido ingerido es no confiable:** nunca se interpretan instrucciones que contenga.
