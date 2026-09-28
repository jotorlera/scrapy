# 04 — Modelo de datos

El esquema inicial completo está en `schema/schema.sql`. Este documento explica **por qué** es así y qué invariantes deben respetarse.

## Principios
1. **Todo es fechado y trazable.** Cada hecho del sistema (afirmación, arista del grafo, posición de un actor, observación de una variable) apunta a un `document` fuente y lleva fecha.
2. **Nunca se borra historia.** Los cambios de estado se registran como revisiones (`claim_revision`, versiones de documentos, `valid_from`/`valid_to` en las aristas). Esto permite reconstruir "qué sabíamos el día X".
3. **Una sola identidad por entidad.** Resolución a Wikidata QID cuando exista; si no, identidad local con alias. La fusión de duplicados se registra.
4. **Embeddings de dimensión fija** (1024, bge-m3). Si se cambia el modelo, se crea columna nueva y se migra; no se mezclan espacios vectoriales.
5. **Separación de niveles epistémicos** en `claim.level`: fact, data, academic, opinion.

## Entidades principales y relaciones

```
source 1─n document n─n event (event_document)
document n─n entity (document_entity)
event 1─n claim 1─n claim_evidence n─1 document
claim 1─n claim_revision
event 1─n frame n─n document (document_frame)
entity n─n entity (edge, tipadas y fechadas)
entity(actor) 1─n position_statement n─1 document
state_variable 1─n state_observation ; state_variable 1─n state_delta n─1 event
forecast_question 1─n forecast ; forecast_question 1─n forecast_score ; forecast_question n─1 event
argument_node/argument_edge (mapas argumentales)
historical_case (ARCHIVO)
note, review_card, reading_log (TALLER, DIETA)
business_unit 1─n exposure_alert n─1 event ; business_unit 1─n decision_log (MANDO)
llm_call, job_run (SALA DE MÁQUINAS)
```

## Series temporales (fuera de Postgres)
Las series macro, de mercado y de conflicto de alta frecuencia van en **Parquet**, particionado por `dataset/año/mes`, y se consultan con DuckDB:
- `data/timeseries/macro/{provider}/{series_id}.parquet`
- `data/timeseries/markets/{asset}.parquet` (OHLCV diario; intradía solo para la vigilancia)
- `data/timeseries/acled/{year}.parquet`
- `data/timeseries/prediction_markets/{venue}/{market_id}.parquet`

Postgres guarda solo las **observaciones de variables de estado** (`state_observation`) derivadas de esas series.

## Taxonomía de variables de estado (semilla; ampliar en `docs/07`)
| Dimensión | Ejemplos de `key` por país |
|---|---|
| POWER | `head_of_government`, `coalition_seat_share`, `approval_rating`, `next_election_date`, `polling_lead` |
| RULES | `constitutional_change_pending`, `major_law_adopted_30d`, `emergency_decree_active`, `court_ruling_major_30d` |
| MONEY | `policy_rate`, `cpi_yoy`, `core_cpi_yoy`, `gdp_qoq`, `unemployment`, `debt_gdp`, `fx_vs_usd`, `10y_yield`, `sovereign_spread`, `reserves_months_imports` |
| FORCE | `acled_events_30d`, `acled_fatalities_30d`, `military_spending_gdp`, `active_conflicts`, `cast_forecast_next_month` |
| LEGITIMACY | `protest_events_30d`, `trust_government`, `vdem_liberal_democracy` |
| EXTERNAL | `unga_alignment_us`, `unga_alignment_china`, `sanctions_active_count`, `treaty_changes_30d`, `diplomatic_ruptures_30d` |
| STRUCTURE | `population_growth`, `median_age`, `energy_import_dependence`, `renewables_share` |

Cada variable define su **regla de cambio material** (`threshold`). Por ejemplo:
- `{"type":"abs","value":0.25}` para tipos: 25 pb o más.
- `{"type":"zscore","window_days":90,"value":2.0}` para eventos de ACLED.
- `{"type":"categorical"}` para cambio de jefe de Gobierno.

## Datos del usuario
`note`, `review_card`, `reading_log`, `business_unit`, `exposure_alert` y `decision_log` son **privados**. Nunca se envían en bloque a un LLM: solo el fragmento mínimo que requiere cada tarea. Se excluyen de cualquier exportación salvo que el usuario la pida explícitamente.
