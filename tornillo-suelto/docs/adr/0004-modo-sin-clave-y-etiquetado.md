# ADR-0004 — Modo sin clave: núcleo determinista y etiquetado de procedencia

**Estado:** aceptada · 2026-09-28

## Contexto
No hay `ANTHROPIC_API_KEY` en el entorno de construcción y, aunque la haya, el presupuesto es de 10 USD/día. La
especificación hace depender del LLM la extracción, los títulos, los marcos, el brief y los análisis.

## Decisión
1. Todos los módulos tienen un **camino determinista** que produce una pantalla útil sin LLM.
2. La capa LLM (`atlas_core/llm.py`) es un único punto de entrada con: modelos por nivel desde
   `config/models.yaml`, presupuesto desde `config/budget.yaml`, registro en `llm_call`, validación Pydantic con
   un reintento y **desactivación limpia** si no hay clave (`LLMUnavailable`), que la API traduce a un estado
   explícito para la UI («Agentes desactivados: añade ANTHROPIC_API_KEY en .env»).
3. Etiquetado de procedencia en datos y UI:
   - `extracted_by = 'heuristic:v1'` frente a `'claude-haiku-4-5-20251001:extractor@1'`.
   - Títulos de evento: `title_source = 'lead_document' | 'llm'`.
   - Brief: `composed_by = 'rules' | 'llm'`.
4. Verificación programática de las salidas del modelo antes de persistirlas: la `quote` de cada afirmación debe
   aparecer literalmente en el texto del documento; si no, se descarta y se cuenta en `llm_call.meta`.

## Consecuencias
- Se puede medir qué aporta el modelo comparando pantallas con y sin clave.
- El coste por día empieza en 0 y crece solo con lo que el usuario active.
