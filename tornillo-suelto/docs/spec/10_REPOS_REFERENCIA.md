# 10 — Repositorios de referencia

Se clonan en `references/` con `bash scripts/clone_references.sh` (git ignora esa carpeta). El agente `investigador-repos` los estudia y escribe `docs/ESTUDIO_REFERENCIAS.md`.

**Regla de licencias:** el código AGPL/GPL **no se copia** al núcleo de ATLAS. Se puede **usar como dependencia instalable** (p. ej. `pip install openbb`) en uso personal y privado, y se pueden **aprender sus patrones** y reescribirlos. Si en algún momento ATLAS se distribuye a terceros, hay que revisar las licencias con un ADR.

| Repo | Qué es | Qué tomamos | Licencia (verificar) |
|---|---|---|---|
| `koala73/worldmonitor` | Dashboard de inteligencia global en tiempo real (TS, Vite, Tauri 2). Doble motor de mapa (globe.gl + deck.gl), índice de inestabilidad por país, radar financiero, IA local con Ollama | **Referencia de UI y mapa**, su catálogo de fuentes (proveedor, nivel, licencia y método de recogida) como insumo del curador, patrones de empaquetado Tauri | AGPL-3.0 |
| `ntamero/globalpulse` | Dashboard autoalojado con Docker, 13 idiomas | Ideas de capas y streams | verificar |
| `SageHourihan/clermont` | Monitor mundial con estética de sala de mando y TUI | Ideas de navegación por teclado | verificar |
| `flairNLP/fundus` | Extractor de noticias de alta calidad (F1 ~97,7 en su benchmark) con extractores por medio | **Dependencia directa** para los medios soportados; respeta las exclusiones anti-IA de los medios | MIT (verificar) |
| `adbar/trafilatura` | Extracción genérica de texto web | **Dependencia directa** (respaldo) | Apache-2.0 (verificar) |
| `mediacloud/*` (api-client, story-indexer, metadata-lib) | Ecosistema Media Cloud: cliente del archivo y directorio, pipeline de ingesta | Cliente API + **directorio de fuentes** por país para ampliar el catálogo; patrones de ingesta a escala | varias (verificar) |
| `madeofpendletonwool/fact-checker` | Motor de afirmaciones con cita obligatoria ("cite-or-drop"), validación adversaria, contradicciones como datos | **Patrón central** del registro de afirmaciones y del auditor | verificar |
| `libr-ai/OpenFactVerification` (Loki) | Pipeline de verificación en 5 etapas | Estructura de etapas de verificación | verificar |
| `idiap/Factual-Reporting-and-Political-Bias-Web-Interactions` | Dataset grande de medios con etiquetas de fiabilidad y sesgo; modelo por grafo de hiperenlaces | Previos de clasificación de fuentes | verificar |
| `Media-Bias-Group/*` | Investigación académica en sesgo mediático (sesgo de cobertura, anotaciones sintéticas) | Métodos para el índice de silencio y los marcos | verificar |
| `VectorInstitute/news-media-bias` | Kit UnBIAS y dataset de 3,7 M filas | Evaluación de clasificadores | verificar |
| `clarin-eric/ParlaMint` | Debates parlamentarios de 29 países y regiones (TEI, TSV), 2015-2022 | Histórico de "dice frente a vota"; entrenamiento de posiciones | CC-BY (datos; verificar) |
| `OpenBB-finance/OpenBB` | Plataforma de datos financieros y macro + `openbb-mcp-server` | **Dependencia directa** para ECONOMÍA y MERCADOS; MCP para los agentes | AGPL-3.0 |
| `TauricResearch/TradingAgents` | Multiagente estilo firma de trading (LangGraph) | Patrón de debate alcista/bajista y roles | Apache-2.0 (verificar) |
| `david188888/TradingAgents` | Fork con Evidence Steward previo al debate y salida en modo investigación sin órdenes | **Patrón preferido** para la mesa de mercados | verificar |
| `IQTLabs/snowglobe` | Wargames abiertos con LLM (In-Q-Tel) | Base conceptual del simulador (Modo A) | verificar |
| `danielrosehill/Geopol-Modeller` | Fork con escenarios y actores de crisis reales y predicciones puntuadas | **Patrón preferido** del simulador | verificar |
| `danielrosehill/AI-Geopol-Projects` | Lista curada de proyectos de IA geopolítica | Mapa del campo | — |
| `666ghj/MiroFish` | Motor de simulación de enjambre sobre OASIS | Modo B (opinión pública), experimental | verificar |
| `camel-ai/oasis` | Simulación social con agentes (base de MiroFish) | Alternativa directa al Modo B | verificar |
| `Jon-Becker/prediction-market-analysis` | Mayor dataset público de Polymarket y Kalshi + indexadores | Backtesting y calibración del motor de pronóstico | verificar |
| `MaartenGr/BERTopic` | Modelado de temas con embeddings | Clustering y temas | MIT (verificar) |

**Si un repositorio no existe o ha cambiado de nombre**, el script lo registra y sigue. El investigador busca la alternativa actual y lo anota.

## Otros recursos (sin clonar; APIs y datasets)
GDELT, ACLED (+ CAST), Polymarket Gamma API, Kalshi API, Metaculus API, Manifold API, EUR-Lex/CELLAR, BOE datos abiertos, Congreso de los Diputados datos abiertos, Parlamento Europeo datos abiertos, congress.gov API, UN Digital Library, OpenAlex, Semantic Scholar, PhilPapers, Stanford Encyclopedia of Philosophy (solo enlace), Project Gutenberg, Perseus, Wikisource, Wikidata, OpenSanctions, V-Dem, Manifesto Project, ParlGov, SIPRI, UCDP, Correlates of War, UN WPP, OWID, FAO, OMS GHO, ClinicalTrials.gov, EU CTR.

## Documentación de Claude a consultar durante la construcción
- Claude Code: extensiones (CLAUDE.md, skills, subagentes, hooks, MCP, plugins): https://code.claude.com/docs/en/features-overview
- Claude Agent SDK (Python) y API de Anthropic (prompt caching, Batch API, salida estructurada): https://docs.claude.com
- Si hay dudas sobre capacidades actuales, usar el subagente de documentación de Claude Code y **no suponer**.
