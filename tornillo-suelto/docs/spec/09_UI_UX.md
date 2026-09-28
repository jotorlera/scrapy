# 09 — UI / UX

## Carácter
Una **terminal profesional de inteligencia**: densa, precisa y serena. Referencias de espíritu (no de copia): Bloomberg Terminal (densidad, teclado), Linear (pulcritud, velocidad), Palantir/Foundry (grafo y mapa), The Economist (tipografía editorial para el texto largo). Se evitan los dashboards genéricos de plantilla, los degradados decorativos y los emojis en la interfaz.

## Sistema de diseño (`packages/ui`)
- **Tema oscuro por defecto y tema claro completo.** Tokens CSS en `:root` con variantes para dark y light.
- **Tipografía:**
  - Interfaz: Inter o IBM Plex Sans.
  - Datos: una monoespaciada con cifras tabulares (JetBrains Mono o IBM Plex Mono).
  - Lectura larga (EVENTOS, ÁGORA, TALLER): una serif editorial legible (Source Serif o Newsreader).
- **Color semántico, no decorativo:**
  - Dominios: política, economía, conflicto, sociedad, tecnología y salud. Paleta categórica accesible y validada para daltonismo.
  - Estados de afirmación: confirmada (verde sobrio), disputada (ámbar), desmentida (rojo), sin verificar (gris). Siempre con icono y texto, **nunca solo color**.
  - Ecosistemas ideológicos: escala divergente neutra (sin rojo y azul partidistas de EE. UU.), para no cargar ideológicamente la lectura.
  - Materialidad: escala secuencial de un solo tono.
- **Densidad:** espaciado compacto por defecto y un modo "cómodo".
- **Movimiento:** mínimo; transiciones de 120-180 ms; sin animaciones de relleno.
- **Accesibilidad:** WCAG 2.1 AA, navegación completa por teclado, foco visible, `prefers-reduced-motion`.

## Layout global
```
┌───────────────────────────────────────────────────────────────────────────────┐
│ ATLAS  [ANALISTA|PENSADOR|CEO]   ⌘K Buscar / preguntar…        ⏱ 07:00 Brief  ⚙ │
├──────┬────────────────────────────────────────────────────────────┬───────────┤
│ Nav  │                  ÁREA PRINCIPAL DEL MÓDULO                 │ Panel     │
│ del  │                                                            │ contextual│
│ modo │                                                            │ (detalle, │
│      │                                                            │ agente en │
│      │                                                            │ streaming,│
│      │                                                            │ notas)    │
├──────┴────────────────────────────────────────────────────────────┴───────────┤
│ Cinta: índices · divisas · materias primas · tipos · mercados de predicción seguidos │
└───────────────────────────────────────────────────────────────────────────────┘
```
- La **navegación** cambia con el modo:
  - Analista: Radar, Eventos, Prisma, Primarias, Economía, Mercados, Geopolítica, Actores.
  - Pensador: Ágora, Archivo, Megatendencias, Taller, Pronósticos.
  - CEO: Mando, Simulador, Brief ejecutivo.
- El **panel contextual** es plegable y muestra el detalle de la selección, las respuestas de agentes con streaming, las notas rápidas y el botón "Añadir a TALLER".

## Interacción
- **Paleta ⌘K** (cmdk): navegar, buscar, lanzar acciones ("profundiza en…", "¿qué ha cambiado en Turquía 7d?", "nuevo pronóstico", "tutor socrático sobre…").
- **Atajos estilo vim/gmail:** `g r` Radar, `g e` Eventos, `g p` Prisma, `g m` Mercados, `g a` Ágora, `g t` Taller, `g c` Mando; `j/k` para moverse en listas, `o` para abrir, `n` para nota, `f` para pronóstico, `?` para la ayuda.
- **Citas interactivas:** cada afirmación tiene un marcador; al pasar el ratón se ve la fuente y la cita literal, y al hacer clic se abre el documento en el panel con el fragmento resaltado.
- **Etiquetas de nivel epistémico** en todas las tarjetas: HECHO, DATO, ACADÉMICO u OPINIÓN.
- **Transparencia:** cada puntuación (materialidad, silencio, inestabilidad, probabilidad) tiene un icono "ⓘ" que muestra su desglose.
- **Streaming de agentes:** los pasos visibles del trabajo (fuentes consultadas y subagentes activos) en un plegable, y el resultado final estructurado.

## Pantallas clave (wireframes a desarrollar en la fase 1-2)
1. **RADAR:** mapa central, deltas a la izquierda, top de eventos a la derecha y cinta abajo.
2. **EVENTO:** cabecera (título neutro, materialidad con desglose, países, dominio, mini-matriz de cobertura), pestañas internas (docs/02 M2) y panel lateral con actores y pronósticos.
3. **PRISMA:** matriz de cobertura a pantalla completa (heatmap), columnas de marcos debajo y léxico diferencial.
4. **FICHA DE PAÍS:** cabecera de variables de estado con sparklines, pestañas y el botón "¿Qué ha cambiado?".
5. **MERCADOS:** árbol de exposición (grafo jerárquico izquierda → derecha), cuadro de "qué está descontado" y estudio de evento.
6. **ÁGORA:** mapa argumental (React Flow) a pantalla completa con un inspector de nodo; lector del canon con subrayado.
7. **PRONÓSTICOS:** lista con probabilidades (usuario, sistema, mercado) en barras comparables y curva de calibración.
8. **MANDO:** tarjetas por negocio con alertas por canal, calendario regulatorio y diario de decisiones.
9. **BRIEF:** diseño editorial de lectura (serif, columna única, ~680 px), exportable a PDF y a email.

## Visualización
- Mapas: MapLibre + deck.gl (Scatterplot, Heatmap, Arc para flujos comerciales y de sanciones, GeoJson para choropleths) y globe.gl como alternativa 3D.
- Grafos: Sigma.js (actores e ideas; miles de nodos) con layout ForceAtlas2 en un worker.
- Series: ECharts o visx con sparklines en tablas.
- Matrices: heatmap propio en canvas para las de cobertura grandes.
- Regla: cada gráfico tiene título, unidades, fuente y fecha visibles.

## Estados vacíos y errores
- Explican qué falta y cómo resolverlo, por ejemplo: "Conecta tu clave de ACLED en Ajustes → Fuentes para ver el mapa de conflicto".
- Si un conector falla, el módulo muestra el último dato válido con su fecha y un aviso discreto. Nunca muestra datos inventados.

## Verificación visual (obligatoria por fase)
Playwright captura cada pantalla en los temas oscuro y claro y en dos anchos (1440 px y 1920 px), y además en 1024 px para la app. El agente `qa-verificador` revisa las capturas antes de cerrar la fase.
