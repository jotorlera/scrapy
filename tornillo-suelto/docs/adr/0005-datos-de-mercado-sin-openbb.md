# ADR-0005 — Datos de mercado y de predicción sin OpenBB

**Estado:** aceptada · 2026-09-28

## Contexto
OpenBB Platform es AGPL-3.0, pesa cientos de MB y arrastra decenas de dependencias. Para la cinta de mercados y
«qué está descontado» bastan tres fuentes públicas sin clave.

## Decisión
- **Cinta de mercados:** endpoint público de gráficos de Yahoo Finance (`query1.finance.yahoo.com/v8/finance/chart`)
  para índices, divisas, materias primas, VIX y bonos. Actualización cada 15 minutos; se guarda la última
  observación válida con su hora.
- **Mercados de predicción:** Polymarket Gamma API y Manifold API (solo lectura). Metaculus responde 403 sin
  cabeceras de navegador; no se implementa en esta entrega (`connectors/prediction_markets.py` solo tiene
  `fetch_polymarket` y `fetch_manifold`).
- **Macro:** FRED requiere clave (gratuita). Conector **pendiente**: `FRED_API_KEY` queda reservada en
  `settings.py` y comentada en `.env.example`, y por ahora no tiene efecto (ningún código la lee). Sin series
  macro, las variables MONEY solo reciben deltas categóricos desde eventos y `fx_vs_usd` desde la cinta
  (`engines/state.py`; ver PROGRESS.md «Deuda técnica» y «Siguiente»).

## Consecuencias
- Cero dependencias AGPL en el núcleo.
- Si un proveedor cambia su API, se cambia un conector de 60 líneas; los motores no se enteran.
- ATLAS nunca opera: no hay integración con brokers ni con la API de trading de ningún mercado.
