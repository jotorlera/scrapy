# 11 — Roadmap

Cada fase tiene: **objetivo**, **entregables**, **criterios de salida** (demostrables) y un **cierre**: tests en verde, `make up` funcionando, capturas revisadas por `qa-verificador`, `PROGRESS.md` actualizado y merge a `main`.

Las duraciones son orientativas para trabajo intensivo con Claude Code. La prioridad es la calidad por encima del calendario.

## Fase 0 — Fundaciones (día 1)
- ADRs de las decisiones clave: formato (web + Tauri), stack, DB, colas, embeddings, niveles de modelo y licencias.
- `references/` clonado y `docs/ESTUDIO_REFERENCIAS.md` escrito.
- Monorepo: `apps/web`, `apps/desktop` (vacío), `services/core`, `services/workers`, `packages/ui`, `packages/schema`, `evals/`, `data/`.
- `docker-compose.yml` (Postgres 16 + pgvector, Redis), `Makefile`, `.env.example`, CI local (lint + tests), pre-commit.
- Migraciones Alembic desde `schema/schema.sql`.
- Registro de LLM (`llm_call`) y de jobs (`job_run`) funcionando desde el primer día.

**Salida:** `make up` levanta todo. `make test` en verde. Existe un endpoint de salud.

## Fase 1 — Ingesta y RADAR mínimo (semana 1)
- `SourceConnector` + conectores `rss`, `sitemap_news`, `fundus`, `trafilatura` y `gdelt`.
- Carga de `config/fuentes.seed.yaml`. El agente `curador-fuentes` autodescubre los feeds de las primeras 150 fuentes y verifica acceso y exclusiones.
- Embeddings bge-m3, deduplicación y clustering incremental de eventos.
- Extractor (Haiku) de entidades y afirmaciones con cita.
- UI: esqueleto con los tres modos, paleta ⌘K, **RADAR** con mapa y top de eventos, y vista básica de **EVENTO** (afirmaciones + fuentes).
- SALA DE MÁQUINAS básica.

**Salida:** 24 h de ingesta real, al menos 30 eventos coherentes en RADAR y afirmaciones con cita navegable.

## Fase 2 — Rigor: primarias, verificación, PRISMA, BRIEF (semanas 2-3)
- Conectores de primarias: EUR-Lex, BOE, Congreso, Parlamento Europeo, BCE, Fed, BdE, ONU y congress.gov. DIFF de documentos.
- Canonicalización y verificación de afirmaciones, estados, revisiones e independencia de fuentes.
- Clasificador de marcos, familias de marcos, índice de silencio y léxico diferencial. **PRISMA** completo.
- Materialidad con desglose y variables de estado (primer lote: POWER, MONEY y FORCE para los países de nivel A).
- Mesa de agentes v1: editor, 3 regionales (UE, España, EE. UU.), auditor y equipo rojo. Flujo F2.
- **BRIEF** diario (tarea programada) en la app y por email.
- Conjunto dorado (`evals/`) con 25 eventos.

**Salida:** Brief real generado dos días seguidos con menos del 2% de afirmaciones no soportadas en la auditoría. PRISMA correcto en el test sintético.

## Fase 3 — Economía, mercados y geopolítica (semanas 4-5)
- OpenBB (SDK + MCP): panel **ECONOMÍA** (40 economías, 12 bancos centrales) y cinta de mercados.
- **MERCADOS:** grafo de canales causales, árbol de exposición, "qué está descontado" y estudios de evento.
- ACLED + CAST, capa de conflicto, puntos de paso, sanciones y votaciones AGNU. **GEOPOLÍTICA** + **FICHAS DE PAÍS** con "¿Qué ha cambiado?".
- Resto de analistas: macro, mercados, conflicto, discurso y regionales restantes.
- Ampliación del catálogo a ~1.500 fuentes y 11 idiomas.

**Salida:** fichas completas de todos los países de nivel A. Estudio de evento de Ucrania 2022 reproducido. Árbol de exposición correcto en 5 eventos.

## Fase 4 — Pronósticos y ACTORES (semanas 6-7)
- Motor de pronóstico completo (docs/06): generación, enlace a mercados, tasas base, ensemble, agregación, resolución, puntuación y calibración.
- Backtest sobre 100 preguntas resueltas.
- **ACTORES:** 200 actores con QID, rastreador de posiciones, dice frente a vota (ParlaMint + API actual), red y predicciones de expertos.
- **SOCIAL:** Bluesky + listas epistemológicas (X opcional).
- **SIMULADOR** Modo C ("¿qué pasa si…?").

**Salida:** 20 preguntas reales en ciclo completo. Panel de calibración operativo. Backtest documentado.

## Fase 5 — Modo PENSADOR completo (semanas 8-9)
- **ÁGORA:** canon (textos de dominio público), traductor normativo, lentes, editor de mapas argumentales (con la RBU sembrada), genealogía, mapa de desacuerdos, tutor socrático y test de Turing ideológico.
- **ARCHIVO:** 150 casos y análogos; tasas base conectadas al motor de pronóstico.
- **MEGATENDENCIAS:** 7 paneles.
- **TALLER:** notas enlazadas, subrayados, Zotero/BibTeX, FSRS, plantillas de ensayo y vigilante de huecos de investigación salud × política.
- **DIETA:** índices, puntos ciegos, steelman y sesgo de confirmación.
- **SIMULADOR** Modo A con 1 escenario real.

**Salida:** el usuario puede pasar de un evento a su cuestión normativa, de ahí al mapa argumental, a la nota y al ensayo exportado, sin salir de la app.

## Fase 6 — Modo CEO y app de macOS (semanas 10-11)
- **MANDO:** registro de negocios, mapa de exposición, radar regulatorio, inteligencia de sector (incluidos ensayos clínicos), diario de decisiones, preparación de reuniones (con Google Calendar opcional) y Brief ejecutivo.
- **App Tauri 2:** icono en la barra de menús con el Brief, notificaciones nativas, atajo global ⌘⇧Espacio para la paleta, arranque de servicios, llavero y firma/notarización si hay cuenta de desarrollador (si no, build local).
- SIMULADOR Modo B (experimental).

**Salida:** app `.app` instalable. Alertas de exposición reales durante una semana. `make desktop` funciona.

## Fase 7 — Robustez y despliegue opcional (continuo)
- Despliegue opcional en un VPS + Tailscale para funcionar 24/7.
- Copias de seguridad cifradas (pg_dump + Parquet) y restauración probada.
- Conjunto dorado de 50 eventos; evaluación de agentes en CI; regresiones de coste.
- Rendimiento: objetivos de docs/01 §8.
- Traducción de la UI al inglés.

## Definición de terminado (global)
1. Funciona con datos reales, no con maquetas.
2. Toda afirmación visible tiene fuente.
3. Tests unitarios, de integración y e2e en verde. Evals sin regresión.
4. Coste medido dentro del presupuesto.
5. Capturas revisadas en tema oscuro y claro.
6. Documentación actualizada: ADR si hubo decisión, `PROGRESS.md` y README de usuario.
