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
  cabeceras de navegador; se deja el conector preparado y desactivado.
- **Macro:** FRED requiere clave (gratuita). El conector se activa con `FRED_API_KEY`; sin ella, ECONOMÍA muestra
  los datos que llegan por comunicados de bancos centrales y el calendario, y lo dice.

## Consecuencias
- Cero dependencias AGPL en el núcleo.
- Si un proveedor cambia su API, se cambia un conector de 60 líneas; los motores no se enteran.
- ATLAS nunca opera: no hay integración con brokers ni con la API de trading de ningún mercado.
