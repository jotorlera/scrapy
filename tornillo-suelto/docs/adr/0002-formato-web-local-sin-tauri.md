# ADR-0002 — Formato de entrega: aplicación web local; Tauri pospuesto

**Estado:** aceptada · 2026-09-28

## Contexto
La especificación recomienda web local-first + envoltorio Tauri 2 (fase 6). Se construye en la nube, sin Mac ni
toolchain de Rust, y el valor del envoltorio (bandeja, notificaciones nativas, llavero) es marginal frente al de
los módulos.

## Decisión
Backend FastAPI que **sirve también el frontend compilado** en `http://127.0.0.1:8765`. Un solo comando (`make up`)
levanta todo. Tauri queda como fase posterior: el frontend ya es una SPA estática, así que envolverla no exige
cambios.

## Consecuencias
- El Brief de las 07:00 se genera con el planificador del proceso; si el Mac está apagado, se genera al arrancar.
- Las notificaciones son en la app (campana) y, opcionalmente, por email cuando se configure.
