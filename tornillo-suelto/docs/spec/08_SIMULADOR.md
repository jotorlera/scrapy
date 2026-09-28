# 08 — Simulador

## Principio rector
**Simular sirve para explorar, no para predecir.** Los propios proyectos de referencia advierten que sus resultados dependen del prompt, del modelo, del orden de turnos y de las reglas, y que no son extrapolables a gobiernos reales. ATLAS usa la simulación para:
1. **Generar escenarios** y trayectorias que alimentan preguntas de pronóstico (docs/06 §6).
2. **Trazar escaleras de escalada** y encontrar puntos de decisión.
3. **Formación en RR. II.:** ver cómo cambian los resultados al cambiar el marco teórico de los agentes (realista, liberal o constructivista).
4. **CEO:** simular reacciones de reguladores, competidores y opinión pública ante una decisión del usuario.

Toda salida del simulador lleva la etiqueta **"SIMULACIÓN — no es predicción"**.

## Modo A: Wargame / crisis multiactor
**Referencias:** IQTLabs/snowglobe (juego abierto con LLM; humanos y agentes con persona; todo el ciclo automatizable) y danielrosehill/Geopol-Modeller (fork con sistema de escenarios y actores para crisis reales, separación motor/escenario, y seguimiento de predicciones puntuadas contra la realidad).

**Diseño:**
- **Escenario** (YAML): situación inicial generada a partir de un evento de ATLAS (afirmaciones confirmadas + variables de estado), actores (6-10), objetivos, líneas rojas, recursos y reglas de adjudicación.
- **Actores:** agentes con persona basada en datos (declaraciones y posiciones de ACTORES, doctrina publicada, historial de conducta de ARCHIVO), no en estereotipos. Cada actor tiene un parámetro `theory_lens` (realist | liberal | constructivist | domestic_politics).
- **Adjudicador:** un agente con un **motor de estado programático** (recursos, territorio, economía, opinión) más adjudicación LLM para lo cualitativo. Esta hibridación es preferible a la adjudicación puramente LLM.
- **Ejecución:** N réplicas (por defecto 20) con variación de semilla, modelo y orden. La salida es una **distribución de desenlaces** con trayectorias tipo y puntos de bifurcación.
- **Humano en el bucle:** el usuario puede jugar un actor.
- **Registro:** cada simulación guarda su escenario, parámetros, turnos y desenlaces. Si la simulación generó preguntas, se enlazan para medir, con el tiempo, si las simulaciones aportan valor predictivo.

## Modo B: Opinión pública y difusión
**Referencia:** 666ghj/MiroFish (sobre OASIS de CAMEL-AI). Construye un "mundo paralelo" a partir de semillas (noticias, borradores de ley, señales financieras) con miles de agentes con personalidad y memoria.

**Diseño en ATLAS:**
- Semilla: un evento o una política (p. ej. un borrador normativo que afecta a los negocios del usuario).
- Población de agentes **calibrada con datos**: distribución de actitudes por encuestas públicas (Eurobarómetro, CIS, Pew) cuando existan. Sin datos, se declara la población como hipotética.
- Salida: distribución de reacciones por segmento, narrativas emergentes y sensibilidad a cambios de mensaje.
- **Coste:** es el módulo más caro. Límite estricto de agentes y turnos, y uso de modelos baratos para los agentes de población.

## Modo C: "¿Qué pasa si…?" rápido
Sin simulación multiagente: un agente de escenarios propone 3-5 trayectorias con probabilidad, desencadenantes y señales tempranas, y el equipo rojo las ataca. Es barato, inmediato y suficiente la mayoría de las veces.

## UI
- Editor de escenario: formulario + YAML avanzado.
- Visualización de turnos en línea temporal, mapa y un grafo de relaciones que cambia por turno.
- Panel de desenlaces con histograma, trayectorias representativas y bifurcaciones.
- Botón "Convertir en preguntas de pronóstico".

## Criterios de aceptación
- Modo C operativo en fase 4. Modo A con 1 escenario real completo (20 réplicas) en fase 5. Modo B experimental en fase 6.
- Etiqueta de simulación siempre visible.
- Coste por simulación registrado y por debajo del presupuesto de docs/12.
