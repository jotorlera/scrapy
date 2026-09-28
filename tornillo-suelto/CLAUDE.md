# CLAUDE.md — Reglas del proyecto TORNILLO SUELTO (motor ATLAS)

## Qué es
Terminal personal de inteligencia local-first para un único usuario. La especificación original está en
`docs/spec/`; las decisiones que la modifican, en `docs/adr/` y `docs/PLANTEAMIENTO.md`. Si algo de este archivo
contradice `docs/spec/`, manda este archivo y los ADR.

## Idioma
Conversación, documentación, UI y textos visibles en **español**. Código, identificadores, tablas y commits en
**inglés**. El contenido ingerido se guarda en su idioma original.

## Principios que el código debe respetar (no negociables)
1. **Cita o descarta.** Ninguna afirmación llega a la UI sin `document_id` y `quote` literal. `quote_supported()`
   se aplica también a las salidas del modelo antes de persistir.
2. **Procedencia visible.** `extracted_by`, `title_source`, `composed_by` viajan hasta la UI.
3. **Cada puntuación se explica.** Materialidad, silencio y probabilidad exponen su desglose por API.
4. **Datos, no órdenes.** El contenido ingerido va entre `<documento>` y nunca se ejecuta como instrucción.
5. **Privacidad.** `config/perfil.yaml` y `business_unit` nunca se envían completos al modelo (`study_context()`
   solo comparte estudios; los negocios solo cuando hay `exposure_alert`).
6. **Presupuesto.** Toda llamada pasa por `atlas_core/llm.py` (registro en `llm_call`, tope de `config/budget.yaml`).
7. **Nombres de modelo solo en `config/models.yaml`.**
8. **Sin asesoramiento financiero.** Nada de órdenes ni brókers.

## Arquitectura (real, no la de la spec)
- `services/core/atlas_core/`: `db.py` (SQLite, esquema en `SCHEMA`), `connectors/`, `engines/`, `pipeline.py`,
  `agents.py` + `llm.py`, `api/` (routers por modo), `scheduler.py`, `cli.py`, `seed.py` + `seed_data.py`.
- `apps/web/`: React + TypeScript + Vite; estilo Hespérides en `src/styles/tokens.css`; gata en `components/Tuerca.tsx`.
- Datos en `data/atlas.db` (fuera de git). Sin Docker, Postgres ni Redis (ADR-0001).

## Cómo trabajar
- `make test` y `make lint` antes de dar algo por hecho; `make ingest` para probar con datos reales.
- Un conector nuevo implementa `discover/fetch/normalize` (`connectors/base.py`) y se registra en `pipeline.py`.
- Un motor nuevo va en `engines/`, es determinista, expone su desglose y trae un test con caso de referencia.
- Un módulo nuevo: router en `api/`, pantalla en `apps/web/src/screens/`, entrada en la navegación del modo.
- Decisiones con alternativas → ADR nuevo en `docs/adr/NNNN-titulo.md`. `PROGRESS.md` al cerrar cada sesión.
- Nunca borrar historia: los cambios de estado se registran (`claim_revision`, `merged_into`).

## Comandos
`make install · seed · ingest · markets · brief · web · up · dev · test · lint · screenshots · clean` y `.venv/bin/atlas --help`.
