# 12 — Legal, seguridad y costes

## 1. Legal y ética de datos
- **Uso personal y privado.** ATLAS no redistribuye contenido de terceros. Si algún día se comercializa o se comparte, hay que revisar las licencias de datos (ACLED, OpenSanctions, Media Cloud, AGPL de OpenBB/WorldMonitor) mediante un ADR y asesoramiento.
- **Medios:** respetar robots.txt, los términos, las reservas TDM y las exclusiones anti-IA. En los medios de pago se guardan titular, entradilla, metadatos y enlace. El texto completo solo si el usuario tiene suscripción, lo configura y es para uso privado.
- **Citas en la UI:** fragmentos breves con enlace al original. Nada de reproducir artículos completos en vistas compartibles o exportables.
- **ACLED:** cuenta propia; atribución según su política; uso no comercial.
- **Mercados de predicción:** solo lectura de datos públicos. **ATLAS nunca opera.**
- **Mercados financieros:** análisis informativo; aviso visible de que no constituye asesoramiento financiero. Nada de órdenes ni de integración con brokers.
- **Datos personales de terceros:** ACTORES solo trata figuras públicas en su dimensión pública (declaraciones, cargos, votos). En la preparación de reuniones se usa solo información pública y profesional. No se construyen perfiles de personas privadas.
- **Redes sociales:** respetar los términos de cada API. X solo con API oficial y de pago si el usuario lo activa.

## 2. Seguridad
- **Prompt injection:** todo contenido ingerido es no confiable. Las medidas son:
  - Preámbulo común en todos los prompts.
  - Herramientas de agentes con permisos mínimos: los agentes de análisis no tienen herramientas de escritura externas ni de red arbitraria.
  - Las acciones con efectos (enviar emails, crear eventos de calendario) requieren confirmación del usuario.
  - Test de regresión con documentos envenenados en `evals/security/`.
- **Secretos:** `.env` fuera de git, llavero de macOS en la app y rotación documentada.
- **Red:** los servicios escuchan solo en localhost (o en Tailscale si se despliega). Sin puertos expuestos a internet.
- **Datos del usuario:** DB local; FileVault; backups cifrados (age o restic). El perfil y los negocios nunca se envían completos a un LLM.
- **Dependencias:** lockfiles, `pip-audit` y `pnpm audit` en CI, y Renovate o Dependabot si hay repo en GitHub.

## 3. Costes (presupuesto por defecto, configurable en `config/budget.yaml`)
Los costes reales dependen de las tarifas vigentes de la API de Anthropic (consultar https://docs.claude.com). Por eso el presupuesto se expresa en **USD/día con tope duro** y el sistema degrada con elegancia al acercarse al límite.

| Partida | Estrategia | Tope inicial sugerido |
|---|---|---|
| Extracción masiva (extractor, marcos, traducción) | Haiku + **Batch API** (descuento) + solo documentos de fuentes Tier ≤3 y eventos candidatos; caché por hash | 40% del presupuesto |
| Análisis de eventos (mesa) | Solo materialidad ≥ 60; máximo N eventos/día; Sonnet; prompt caching del preámbulo y del contexto | 30% |
| Brief diario + revisión dominical | Opus para la síntesis final; resto Sonnet | 10% |
| Pronósticos | Ensemble N=5 con Sonnet + agregador Opus; actualizaciones escalonadas por horizonte | 10% |
| Bajo demanda (profundiza, tutor, simulador) | Presupuesto por acción visible antes de lanzar | 10% |

- **Tope diario por defecto: 10 USD/día**, ajustable por el usuario en Ajustes. Al 80% se pausan las tareas no críticas; al 100% solo quedan la ingesta sin LLM y el Brief.
- **Medición:** cada llamada registra tokens (incluida la caché) y coste. SALA DE MÁQUINAS muestra el gasto por módulo y día y la proyección mensual.
- **Reducción de coste:** caché semántica de respuestas, deduplicar antes de extraer, resúmenes jerárquicos (documento → evento → Brief) y embeddings locales gratuitos.
- **Otras APIs:** la mayoría son gratuitas (GDELT, EUR-Lex, BOE, OpenAlex, Wikidata, FRED con clave). ACLED es gratuita con registro para uso no comercial. X es de pago y opcional. Los proveedores premium de OpenBB son opcionales.
- **Límite de ejecución de Claude Code:** preguntar al usuario solo si una acción implica un gasto recurrente por encima del tope configurado.
