# 06 — Motor de pronóstico

## Fundamento
Estado del arte a septiembre de 2026. Según el Forecasting Research Institute (julio de 2026), los mejores sistemas de IA probablemente han alcanzado la paridad con los superforecasters en ForecastBench. Todos los que lo logran usan un **pipeline**, no un modelo suelto:
1. Generar subpreguntas y búsquedas.
2. Recuperar contexto reciente filtrado por relevancia y fecha.
3. Generar un ensemble de pronósticos con varios modelos.
4. Agregar con un modelo que evalúa los razonamientos.

Aun así, en un benchmark sin contaminación (Mundial 2026, 104 partidos) ningún modelo puntero superó el Brier del mercado de apuestas. **Conclusión de diseño: el mercado es la referencia a batir, y el sistema debe justificar cada desviación del mercado.**

## 1. Ciclo de vida de una pregunta
```
evento material / usuario / plantilla recurrente
  → GENERACIÓN (editor + analistas proponen; filtro de calidad)
  → ENLACE a mercados existentes (Polymarket, Kalshi, Manifold, Metaculus) por similitud semántica + verificación
  → TASA BASE (historiador + ARCHIVO) + CAST (si es conflicto)
  → PRONÓSTICO DEL USUARIO (se pide ANTES de mostrar el del sistema; opcional)
  → ENSEMBLE (N=5 por defecto; enfoques de prompts/runtime/superpronosticador.md)
  → AGREGACIÓN
  → ACTUALIZACIÓN periódica (diaria si la pregunta cierra en menos de 30 días; semanal si no) y ante eventos relacionados de materialidad alta
  → RESOLUCIÓN (automática si la fuente es estructurada; asistida por agente + confirmación del usuario si no)
  → PUNTUACIÓN y calibración
```

## 2. Calidad de las preguntas (filtro obligatorio)
Cada pregunta necesita:
- **Criterio de resolución inequívoco.** Fuente concreta, umbral y definición.
- **Fecha de cierre y de resolución.**
- **No trivial:** la tasa base está entre el 3% y el 97%.
- **Pertinente:** enlaza a un evento, actor, país o negocio del usuario.
- **No duplicada:** similitud con preguntas abiertas por debajo del umbral.

Plantillas recurrentes, que siempre existen:
- Próxima decisión de cada banco central (Fed, BCE, BoE, BoJ, CBRT, Banxico).
- IPC del próximo mes en EE. UU., la eurozona y España (por encima o debajo del consenso).
- Elecciones de los próximos 6 meses (ganador y umbral de escaños).
- Umbrales ACLED en los conflictos principales.
- Altos el fuego.
- Aprobación de leyes en seguimiento.
- Precio del Brent por encima o debajo de un umbral al fin de trimestre.

## 3. Agregación
Para *p_i* pronósticos del ensemble con pesos *w_i* (inicialmente iguales; después según el historial por dominio):

```
logit_agg = Σ w_i · logit(p_i) / Σ w_i
p_ens = sigmoid(a · logit_agg)            # extremización, a ≈ 1.5–2.5 (estimado por calibración histórica; empezar en 1.5)
```

Si hay mercado líquido (volumen por encima del umbral configurable) con probabilidad *m*:

```
p_final = sigmoid( α · logit(p_ens) + (1-α) · logit(m) )
```

α se aprende por dominio minimizando el Brier histórico. El valor inicial es 0,4 (se da más peso al mercado). El agregador LLM (rol B) puede proponer un ajuste, pero debe justificarlo, y el ajuste queda registrado aparte (`forecaster='atlas_llm_adjusted'`) para medir si aporta.

**Se registran siempre por separado**, para saber qué aporta cada pieza: `atlas_ensemble_raw`, `atlas_ensemble_extremized`, `atlas_final`, `market:<venue>`, `acled_cast`, `base_rate`, `user`.

## 4. Puntuación y calibración
- **Brier** binario: (p − o)². Multiclase: suma sobre clases.
- **Log score** (con recorte en [0,01; 0,99]).
- **Brier Skill Score** frente a la tasa base y frente al mercado: BSS = 1 − Brier/Brier_ref.
- **Curva de calibración:** 10 intervalos, con intervalos de confianza de Wilson y la descomposición de Murphy (fiabilidad, resolución, incertidumbre).
- Paneles por dominio, región, horizonte y pronosticador (usuario, sistema, cada agente, expertos seguidos, medios).
- **Puntuación de expertos y medios:** cuando un actor o medio hace una predicción explícita, se extrae como `forecast` con `forecaster='expert:<id>'`. Las predicciones vagas ("podría haber recesión") se marcan como no puntuables y se cuentan aparte: también es información.

## 5. Protocolo del usuario (formación)
- Antes de ver la probabilidad del sistema, el usuario introduce la suya (se puede saltar).
- Tras resolverse, la tarjeta muestra el error y la explicación.
- Cada domingo: calibración, las 3 peores predicciones y qué evidencia se ignoró.
- Micro-ejercicios de estimación (Fermi) y de tasas base, integrados en TALLER (repaso espaciado).

## 6. Integración con el simulador
Las simulaciones (docs/08) generan **distribuciones de trayectorias**. Estas no se convierten directamente en probabilidades. Se usan como:
- Fuente de **escenarios** para las preguntas: nuevas preguntas o nuevas subpreguntas.
- **Evidencia cualitativa** que el ensemble puede citar, con peso limitado y marcada como "simulación".

## 7. Criterios de aceptación
- Ciclo completo funcionando en 20 preguntas reales.
- Enlace automático con mercados con precisión ≥ 90% (verificación manual).
- Backtest retrospectivo sobre 100 preguntas ya resueltas, usando solo información anterior a la fecha de cierre para evitar fugas de información, que reporte el Brier del sistema, la tasa base y el mercado.
- Panel de calibración operativo.
