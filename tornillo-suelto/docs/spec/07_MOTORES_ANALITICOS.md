# 07 — Motores analíticos

## 1. Clustering de eventos (incremental y multilingüe)
- Embedding bge-m3 de `title + lede + primeros 512 tokens`.
- Para cada documento nuevo: vecinos más cercanos entre los **centroides de eventos activos** (últimos 7 días, o 30 días para historias largas). Si la similitud coseno supera θ (calibrar; empezar en 0,78) **y** hay coincidencia de al menos una entidad principal **y** la fecha es coherente, se asigna al evento. Si no, se crea un evento candidato.
- Se reconsolida cada hora con HDBSCAN sobre la ventana de 48 h para fusionar o dividir eventos, registrando `merged_into`.
- **Historias largas:** los eventos se agrupan bajo `parent_event_id` ("Guerra en Ucrania", "Elecciones EE. UU. 2028").
- Título neutro generado por Haiku a partir de las afirmaciones confirmadas, no de los titulares.
- **CA:** pureza ≥ 0,9 y fragmentación ≤ 1,3 en el conjunto dorado.

## 2. Materialidad (0-100)
```
M = 100 · σ( β0
      + β1·Δstate      # suma normalizada de state_delta.magnitude de las variables tocadas
      + β2·power       # poder de los actores implicados (PIB/población/capacidad militar/rol institucional; log)
      + β3·irrevers    # irreversibilidad: ley adoptada, muerte, anexión, default, sentencia firme (clasificador)
      + β4·breadth     # nº de países afectados / bloques
      + β5·primary     # existencia de documento primario que lo formaliza
      + β6·novelty     # distancia a eventos previos del mismo parent
      + β7·user_rel    # relevancia para el usuario: países nivel A, cursos, negocios (acotado para no dominar)
      − β8·virality_only )  # penalización si el volumen de cobertura es alto sin Δstate
```
- Pesos iniciales razonables en `config/materiality.yaml`. Se ajustan con feedback: el usuario marca "importante" o "ruido" y se hace una regresión logística periódica.
- El desglose se guarda en `materiality_breakdown` y **se muestra en la UI** (transparencia).

## 3. Afirmaciones: verificación
1. El extractor produce afirmaciones con cita literal.
2. **Canonicalización:** se agrupan afirmaciones equivalentes entre documentos (embeddings + LLM de desempate) en un `claim` con múltiples `claim_evidence`.
3. **Priorización** por `check_worthy` × materialidad del evento.
4. **Verificación:** búsqueda dirigida en `atlas-primary` y fuentes de Tier 1. La postura de cada evidencia la decide el LLM con la cita a la vista, **y** reglas deterministas para los números (tolerancia, unidades, periodo).
5. **Estado:** `confirmed` si hay primaria o al menos 2 fuentes independientes de Tier ≤2 sin contradicción creíble; `disputed` si hay contradicción entre fuentes creíbles; `refuted` si la primaria contradice; `unverified` en el resto.
6. Cada cambio de estado genera `claim_revision`. Se registra qué medios publicaron la versión luego corregida y si rectificaron (métrica `corrections_rate` por medio).
- **Independencia:** dos medios que reproducen la misma agencia **no** cuentan como independientes (detección por simhash de párrafos y atribución "según Reuters/AFP/EFE…").

## 4. Cobertura, ecosistemas y silencios
- **Ecosistemas:** agrupaciones de fuentes por `ideology_label_local`, por `region_bloc` y por `state_relation`.
- **Volumen esperado** del evento *e* en el ecosistema *k*:
  `E_k = V_e · s_k · r_k(e)`
  donde *V_e* es el volumen total del evento, *s_k* la cuota de producción base del ecosistema (media 30 días) y *r_k(e)* un ajuste de relevancia geográfica y temática aprendido con el histórico de cobertura por país y tema.
- **Índice de silencio** `S_k = (E_k − O_k) / sqrt(E_k)` (residuo de Poisson estandarizado). Se marca cuando `S_k > 2` y `E_k ≥ 5`.
- **Test sintético obligatorio:** un evento inyectado solo en un ecosistema debe disparar el índice en los demás.

## 5. Marcos y narrativas
- Marcos por artículo (clasificador de marcos, Entman) → embeddings de la concatenación problema|causa|juicio|remedio → clustering en familias de marcos por evento (3-6).
- El analista de discurso etiqueta las familias y el vocabulario diferencial se calcula con log-odds ratio con prior informativo (Monroe et al., 2008) por ecosistema.
- **Posición en el tema** por artículo (−1..1) y agregado por autor → perfil de autor.

## 6. Variables de estado y deltas
- Taxonomía en docs/04. Cada variable tiene un **extractor** (serie de OpenBB, ACLED, API oficial o afirmación confirmada) y una **regla de cambio material**.
- Un delta genera `state_delta`, se enlaza al evento que lo explica (si existe) y alimenta RADAR.

## 7. Transmisión geopolítica → mercados
- **Grafo de canales causales** editable (`config/causal_channels.yaml` + UI), sembrado con canales clásicos:
  - Petróleo → inflación general → expectativas de tipos → divisas de importadores netos.
  - Conflicto en un punto de paso → fletes → márgenes de importadores → sectores.
  - Sanciones → cadenas de suministro de un insumo → productores alternativos.
  - Riesgo país → diferencial soberano → bancos domésticos.
  - Aversión al riesgo global → USD/CHF/JPY/oro → emergentes.
  - Decisión de un banco central → curva → sectores sensibles a tipos.
- **Exposición de empresas** por ingresos geográficos (informes anuales o 10-K cuando estén disponibles vía OpenBB o SEC), proveedores (cuando haya dato) y regulación.
- **Estudio de evento:** retornos anormales frente a un modelo de mercado (estimación en [-250, -30]); ventanas estándar; análogos desde ARCHIVO.
- **Lo que descuenta el precio:** volatilidad implícita frente a realizada, curvas y mercados de predicción.

## 8. DIETA (anti-burbuja)
- **Entropía de Shannon normalizada** de la distribución del tiempo de lectura por eje (ideología local, región, idioma, tipo de fuente), en ventanas de 7 y 30 días.
- **Punto ciego:** tema con al menos X minutos leídos y más del 80% en un solo ecosistema o marco → alerta con **steelman** del marco menos leído (lo genera el filósofo o el analista de discurso con las mejores fuentes de ese marco).
- **Sesgo de confirmación:** proporción de subrayados y guardados cuyo `stance` coincide con el de las notas previas del usuario sobre el tema, frente a la proporción disponible.
- Todo es visible, explicable y desactivable.

## 9. Repaso espaciado
Algoritmo FSRS (implementación abierta disponible en Python/TS). Las tarjetas se generan desde notas, conceptos del grado, datos clave de ECONOMÍA y resoluciones de pronósticos ("¿qué probabilidad diste a X y qué pasó?").
