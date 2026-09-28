# 02 — Módulos

Formato por módulo: **propósito**, **pantalla**, **funciones**, **datos/motores**, **criterios de aceptación (CA)**. Los criterios son verificables; un módulo no está terminado sin ellos.

Los elementos **transversales**, presentes en todos los modos, van al final: barra universal y copiloto, Brief, DIETA (anti-burbuja), alertas y SALA DE MÁQUINAS.

---

## MODO ANALISTA

### M1. RADAR — "Qué ha cambiado"
**Propósito:** pantalla de inicio. Muestra cambios materiales en el mundo, no titulares.

**Pantalla:**
- **Centro:** mapa mundial (MapLibre/deck.gl) con conmutador a globo 3D. Cada punto es un **evento** con tamaño según materialidad, color según dominio (política, economía, conflicto, sociedad, tecnología, salud) y halo si ha escalado en las últimas 24 h.
- **Barra superior:** ventana temporal (1 h, 6 h, 24 h, 7 d, 30 d), filtros de dominio y región, y el modo activo.
- **Columna izquierda:** "Deltas", la lista de variables de estado que han cruzado su umbral. Por ejemplo: "Turquía · DINERO · tipo oficial +250 pb", "Etiopía · FUERZA · eventos ACLED ×3 vs. media 90 d".
- **Columna derecha:** los 15 eventos por materialidad. Cada tarjeta muestra: titular neutro generado, países, dominio, materialidad (0-100), nº de fuentes, reparto por ecosistema en mini-barra, nº de fuentes primarias, idiomas, y los iconos 🔮 si hay pronóstico abierto y 🏢 si afecta a los negocios del usuario.
- **Franja inferior:** cinta de mercados (índices, divisas, materias primas, VIX, rendimiento del bono a 10 años de EE. UU. y Alemania, oro, Brent) y probabilidades de mercados de predicción de las preguntas que el usuario sigue.

**Funciones:** clic en un evento abre EVENTOS. Clic en un país abre su ficha en GEOPOLÍTICA. Atajo `g r`. Se actualiza en vivo por WebSocket.

**Datos/motores:** eventos, materialidad, variables de estado, series de mercado (OpenBB), mercados de predicción.

**CA:**
- Con datos reales de 24 h se muestran al menos 30 eventos agrupados correctamente. En una revisión manual de 20 eventos, al menos el 90% de los clusters son coherentes.
- Los deltas enlazan a la serie de la variable y a su fuente.
- Carga en menos de 1,5 s.

### M2. EVENTOS — Registro de afirmaciones
**Propósito:** entender un acontecimiento con trazabilidad total.

**Pantalla (pestañas internas):**
1. **QUÉ HA PASADO:** de 5 a 8 afirmaciones establecidas. Cada una con estado (✅ confirmada / ⚠️ disputada / ❌ desmentida / ⏳ sin verificar), fuente primaria enlazada si existe, primera fuente que la publicó y hora.
2. **LO QUE SABEMOS / LO QUE NO SABEMOS:** preguntas abiertas explícitas.
3. **AFIRMACIONES DISPUTADAS:** cada afirmación con las fuentes a favor y en contra, lado a lado, y la evidencia que aporta cada una.
4. **CRONOLOGÍA:** línea temporal de hechos y de **revisiones** (cuándo cambió el estado de cada afirmación; qué medios corrigieron y cuáles no).
5. **FUENTES:** lista agrupada por tipo (primaria, agencia, medio, opinión, social), por ecosistema y por idioma. Traducción bajo demanda con el original siempre visible.
6. **CONTEXTO:** eventos relacionados, antecedentes (enlace a ARCHIVO), actores implicados (ACTORES) y variables de estado afectadas.
7. **IMPACTO:** exposición de mercados (MERCADOS) y de los negocios del usuario (MANDO), si la hay.
8. **PRONÓSTICOS:** preguntas generadas a partir del evento, con la probabilidad del sistema, la del mercado de predicción y la del usuario.

**Funciones:** "Explícamelo en 60 s", "Profundiza" (lanza un agente analista con streaming), "¿Qué diría X?" (lentes teóricas, enlaza a ÁGORA), "Hacer pronóstico".

**CA:**
- Ninguna afirmación sin fuente.
- En eventos de Tier 1 con documento oficial, la primaria aparece enlazada en al menos el 70% de los casos.
- El historial de revisiones funciona: si cambia el estado de una afirmación, queda registrado con fecha y evidencia.

### M3. PRISMA — Narrativas, silencios y geografía de la cobertura
**Propósito:** ver cómo y quién cuenta cada historia, y quién no la cuenta.

**Pantalla:**
- **Matriz de cobertura:** filas por ecosistema (ideológico: izquierda, centro-izquierda, centro, centro-derecha, derecha, heterodoxo) y columnas por región o idioma (anglosajón, UE, España, Latam, mundo árabe, Turquía, Rusia, China, India, Japón y Corea, África, otros). Cada celda muestra volumen normalizado y color de **índice de silencio** (ver docs/07).
- **Marcos:** de 3 a 6 marcos detectados. Cada uno con atribución causal, juicio moral, remedio propuesto, evidencia que aporta, medios que lo usan (con su peso) y frases representativas (máximo una por medio, cortas, con enlace).
- **Vocabulario diferencial:** términos que distinguen a cada ecosistema, por ejemplo "ocupación" frente a "presencia" o "reforma" frente a "recorte", con frecuencias.
- **Medios estatales:** marcados como tales, con su relación con el Estado (control, alineamiento o servicio público independiente).
- **Evolución:** cómo cambian los marcos dominantes con el tiempo en ese evento.

**Funciones:** "Muéstrame el marco que menos he leído" (anti-burbuja), comparar dos medios concretos, exportar la matriz para un trabajo de clase.

**CA:**
- La matriz se genera para cualquier evento con 20 o más fuentes.
- Los marcos se agrupan entre artículos, no uno por artículo.
- El índice de silencio es estadísticamente sensato: la prueba con un evento sintético "solo cubierto por un ecosistema" lo detecta.

### M4. PRIMARIAS — Monitor de fuentes oficiales
**Propósito:** vigilar la fuente del hecho antes que su interpretación.

**Pantalla:**
- Flujo de documentos oficiales nuevos, filtrable por jurisdicción (ES, UE, EE. UU., ONU, bancos centrales, tribunales, otros países de nivel A) y tipo (ley/reglamento, borrador, sentencia, comunicado, discurso, estadística, votación).
- **Vista DIFF:** comparación borrador ↔ versión final o comunicado ↔ comunicado anterior (p. ej. dos comunicados del BCE), con resaltado y un resumen semántico de qué cambia materialmente.
- **Votaciones:** quién votó qué y su coherencia con lo que dijo (enlaza a ACTORES).
- **Calendario:** consultas públicas, entradas en vigor, reuniones de bancos centrales, cumbres, elecciones.

**CA:**
- Al menos 10 jurisdicciones o instituciones activas en la fase 2.
- El diff funciona sobre dos comunicados reales del BCE o la Fed.
- Las alertas por palabra clave o tema de `perfil.yaml` llegan en menos de 1 h.

### M5. ECONOMÍA — Panel económico mundial
**Propósito:** el estado de la economía mundial y sus cambios.

**Pantalla:**
- **Mapa de calor macro** de las 40 principales economías: PIB (trimestral e interanual), inflación general y subyacente, desempleo, saldo fiscal, deuda/PIB, cuenta corriente, tipo oficial, tipo real y PMI si está disponible.
- **Bancos centrales:** Fed, BCE, BoE, BoJ, PBoC, SNB, Banxico, BCB, RBI, CBRT y otros. Muestra tipo actual, próxima reunión, **expectativas descontadas** (futuros y OIS cuando haya datos, o mercados de predicción) y diff de comunicados.
- **Sorpresas:** dato frente a consenso, con un índice de sorpresa por economía cuando haya consenso disponible; si no, frente a la media de pronósticos de organismos.
- **Comercio y materias primas:** petróleo, gas (TTF, Henry Hub), grano, cobre, litio, tierras raras y fletes. Enlazadas a puntos de paso y sanciones.
- **Monitor de deuda soberana:** diferenciales, CDS si hay proveedor y calendario de vencimientos.
- **Concepto del día:** cada dato relevante etiquetado con el concepto del grado que ilustra (trilema de Mundell, curva de Phillips, dominancia fiscal, equivalencia ricardiana…), con enlace a ÁGORA o TALLER.

**Datos:** OpenBB (FRED, BCE, FMI, OCDE, Banco Mundial, Eurostat, INE vía API propia, BIS), fuentes oficiales y mercados.

**CA:**
- Panel operativo con 40 economías y 12 bancos centrales.
- Cada cifra muestra fuente y fecha del dato.
- El panel "qué ha cambiado" de 7 días funciona.

### M6. MERCADOS — Transmisión de geopolítica a mercados
**Propósito:** entender qué descuenta el mercado y cómo se transmite un evento a los activos. **No es un recomendador**: la UI lo indica de forma permanente.

**Pantalla:**
- **Árbol de exposición** del evento seleccionado: evento → materias primas / divisas / tipos → sectores → empresas expuestas (por ingresos geográficos, cadena de suministro o regulación). Se construye con el grafo de canales causales y datos de exposición.
- **Qué está descontado:** volatilidad implícita (VIX, MOVE si hay dato, volatilidad de activos concretos), curvas de futuros, diferenciales, mercados de predicción y posicionamiento (COT de la CFTC).
- **Estudios de evento:** reacción histórica de estos activos en episodios análogos (enlaza a ARCHIVO), con retornos anormales en ventanas de [-1, +1], [-1, +5] y [-1, +20] días.
- **Carteras de escenario en papel:** el usuario define escenarios (A/B/C con probabilidad) y una exposición que reflejaría cada uno. Se hace seguimiento, se registra y se puntúa. Nunca hay órdenes reales.
- **Vigilancia del usuario:** lista de activos y sectores de interés (incluidos los de sus negocios), con alertas por evento.
- **Mesa de debate** (opcional, agente): análisis alcista frente a bajista de un activo, con auditor de evidencia previo. Inspirado en TradingAgents, pero con salida en modo investigación, **sin órdenes**.

**CA:**
- Para cinco eventos reales, el árbol de exposición muestra al menos tres niveles con sus fuentes.
- El estudio de evento reproduce correctamente un caso conocido, como la reacción del petróleo a la invasión de Ucrania en febrero y marzo de 2022.
- El aviso de "no es asesoramiento financiero" es visible en el módulo.

### M7. GEOPOLÍTICA y PAÍSES
**Propósito:** conflicto, poder y posición internacional; fichas vivas por país.

**Pantalla GEOPOLÍTICA:**
- Mapa de conflicto con **ACLED** (eventos por tipo: batallas, violencia contra civiles, explosiones/violencia remota, protestas, disturbios, desarrollos estratégicos) y el pronóstico **CAST** a 1-6 meses por país.
- Puntos de paso marítimos (Ormuz, Bab el-Mandeb, Suez, Malaca, Bósforo, Panamá, Taiwán, Gibraltar) con estado y eventos cercanos.
- Sanciones (OpenSanctions + listas oficiales), votaciones en la AGNU (matriz de alineamientos y distancia ideal-point), gasto militar (SIPRI), alianzas y tratados.
- **Índice de inestabilidad ATLAS** por país: compuesto transparente de componentes visibles (conflicto, protesta, economía, instituciones, choque externo), con pesos editables. Nunca es una caja negra.

**Ficha de PAÍS** (una por país; profunda para los de nivel A de `config/paises.yaml`):
- Cabecera: variables de estado actuales y su tendencia.
- Pestañas: Política (gobierno, coalición, encuestas, próximas elecciones, instituciones), Economía, Política exterior, Fuerza, Legitimidad, Demografía, Energía y Últimos eventos.
- **Botón "¿Qué ha cambiado?":** 24 h, 7 d, 30 d y 1 año. Devuelve las N cosas que han cambiado **materialmente**, cada una con su fuente.
- Cómo lo cuenta la prensa del propio país frente a la prensa extranjera (miniPRISMA).
- Pronósticos abiertos sobre el país.

**CA:**
- Fichas completas para todos los países de nivel A.
- "¿Qué ha cambiado?" produce un resultado sin afirmaciones sin fuente.
- La capa ACLED carga con filtros de fecha y tipo.

### M8. ACTORES y SOCIAL
**Propósito:** personas e instituciones, lo que dicen frente a lo que hacen, y su historial de aciertos.

**Pantalla de ACTOR:**
- Cabecera: rol actual, organización, país, tradición intelectual (enlace a ÁGORA), QID de Wikidata.
- **Rastreador de posiciones:** por tema (migración, impuestos, Ucrania, UE, RBU, China, clima, IA…), una línea temporal de declaraciones con cita breve, fecha y fuente, y una posición estimada en ejes multidimensionales. Se marcan los **cambios de posición** con su evidencia.
- **Dice frente a vota o hace:** declaraciones enfrentadas a votaciones o decisiones (ParlaMint o ParlaCAP para el histórico europeo y APIs parlamentarias para lo actual).
- **Red:** con quién se relaciona, quién lo financia y qué think tank lo asesora (grafo Sigma).
- **Historial de predicciones:** predicciones que hizo, cuáles se han resuelto y su Brier score.
- Contradicciones fechadas, siempre con la fuente original.

**SOCIAL — listas epistemológicas:**
- Listas curadas (economistas, teoría política, geopolítica, defensa, instituciones UE, política EE. UU., política española, Oriente Medio, China, Rusia, IA, energía, mercados, salud global).
- Cada cuenta tiene ficha: área de pericia, orientación, tipo (fuente primaria o comentarista), historial de predicciones y correcciones.
- Fuentes: Bluesky (AT Protocol, abierto) como base. X mediante API de pago opcional, limitada a las listas. Mastodon y Substack por RSS.
- **No existe feed infinito.** Solo resúmenes por lista y alertas cuando una cuenta de fuente primaria (un ministerio, un portavoz) publica algo material.

**CA:**
- 200 actores sembrados con QID.
- El rastreador de posiciones funciona para 20 actores y 8 temas.
- La vista "dice frente a vota" funciona para al menos un parlamento con datos actuales.

---

## MODO PENSADOR

### M9. ÁGORA — Filosofía, ideas y argumentos
**Propósito:** la capa que da sentido a todo lo demás. Conecta la actualidad con la teoría y forma el criterio propio del usuario.

**Submódulos:**
1. **Canon vivo.** Textos primarios de dominio público (Project Gutenberg, Perseus, Wikisource) con lector integrado, subrayado y notas. Referencia a la Stanford Encyclopedia of Philosophy y a la Internet Encyclopedia of Philosophy (se enlaza, no se reproduce). PhilPapers para literatura académica. Bibliografía del grado en `perfil.yaml`: para las obras con derechos solo se guardan metadatos, notas del usuario y citas breves.
2. **Traductor normativo.** Cada evento material recibe de 1 a 3 cuestiones normativas con la tradición relevante. Ejemplos: guerra → *jus ad bellum/in bello*; presupuesto → justicia distributiva (Rawls, Nozick, Sen); migración → soberanía frente a cosmopolitismo; banco central → legitimidad tecnocrática; IA → libertad, riesgo y paternalismo; salud pública → libertad individual frente a bien común.
3. **Lentes.** "¿Cómo lo interpretaría…?" desde marxismo, liberalismo clásico, rawlsianismo, libertarismo, republicanismo (Pettit), comunitarismo, conservadurismo (Burke, Oakeshott), realismo (Morgenthau, Waltz, Mearsheimer), liberalismo institucionalista (Keohane), constructivismo (Wendt), teoría crítica y escuela de Viena. Cada lente cita obras concretas y marca claramente que es una **reconstrucción**.
4. **Mapas argumentales.** Editor de grafos (React Flow) con nodos tipados: tesis, premisa, objeción, réplica, evidencia empírica, autor, obra. Cada arista es de apoyo o de ataque. Detecta premisas no apoyadas y circularidad. Los nodos del usuario se guardan con fecha, lo que muestra la evolución de su pensamiento. Semilla: RBU (Van Parijs → libertad real; objeción de reciprocidad [usuario]; Atkinson → renta de participación; Hayek → suelo mínimo; evidencia empírica de Finlandia, Kenia/GiveDirectly, Stockton).
5. **Genealogía de ideas.** Grafo de conceptos e influencias (por ejemplo, la libertad de Hobbes → Locke → Constant → Mill → Berlin → Pettit). Conectado a actores actuales: qué tradición hay detrás de cada líder o partido.
6. **Mapa de desacuerdos.** Posiciones reales de la profesión (encuesta de PhilPapers) frente a lo que el usuario cree que es consenso.
7. **Tutor socrático y sparring.** Diálogo en el que el tutor pregunta en lugar de responder; debate contra la reconstrucción de un autor con citas; modo examen de 10 minutos defendiendo una tesis contra objeciones crecientes. Evaluación con rúbrica (claridad, validez, uso de evidencia, anticipación de objeciones).
8. **Test de Turing ideológico.** El usuario escribe la posición contraria; el sistema evalúa si un defensor real la firmaría.

**CA:**
- El traductor normativo aplicado a 20 eventos da cuestiones pertinentes en al menos el 85% de los casos (revisión humana).
- Editor de mapas funcional, con el mapa de la RBU sembrado.
- Las lentes citan obras reales, con verificación básica de que la obra existe (Wikidata u OpenLibrary).
- Tutor socrático operativo.

### M10. ARCHIVO — Historia y precedentes
**Propósito:** analogías históricas estructuradas y tasas base.

**Funciones:**
- Base de casos históricos codificados: crisis de deuda, transiciones de hegemonía, guerras comerciales, sanciones, golpes de Estado, revoluciones, hiperinflaciones, pandemias, referendos de secesión, colapsos de alianzas. Para cada uno: variables, desenlace, duración y fuentes.
- Datasets de apoyo: Correlates of War, UCDP, Polity o V-Dem, Reinhart-Rogoff (crisis), Global Sanctions Data Base y episodios de alto el fuego. Verificar la licencia de cada uno.
- Ante un evento nuevo, propone los 3-4 precedentes más similares **y en qué difieren** (tabla de similitudes y diferencias). Alimenta la **clase de referencia** del motor de pronóstico.
- Alerta contra analogías fáciles: si el usuario o un medio invoca una analogía ("Múnich 1938"), la herramienta evalúa su ajuste.

**CA:**
- Al menos 150 casos sembrados.
- Recuperación de análogos con justificación.
- El motor de pronóstico consume sus tasas base.

### M11. MEGATENDENCIAS
**Propósito:** fuerzas lentas que dominan el largo plazo.

**Funciones:**
- Paneles de series largas y proyecciones: demografía (UN WPP), energía y emisiones (AIE, Ember, OWID), deuda (FMI), urbanización, agua y alimentos (FAO), tecnología e IA (indicadores de inversión y capacidad de cómputo cuando existan), salud y envejecimiento (OMS, IHME/GBD).
- Cada evento se etiqueta por si **acelera o frena** alguna megatendencia.

**CA:** 7 paneles con fuente y fecha, y la etiqueta de acelera/frena en eventos de materialidad alta.

### M12. TALLER — Segundo cerebro y producción
**Propósito:** convertir la información en obra propia.

**Funciones:**
- Notas atómicas (TipTap) con enlaces `[[entidad]]` al grafo y retroenlaces.
- Subrayados desde cualquier artículo, documento o texto del canon.
- Integración con gestor bibliográfico (Zotero vía API o BibTeX) y con las lecturas de cada asignatura.
- **Repaso espaciado** (algoritmo FSRS) de conceptos, datos, autores y fechas. Las tarjetas se generan desde notas y eventos.
- **Producción:** plantillas de ensayo para la carrera (firma "Dr. José Francisco Tornero-Aguilera"), columna, post y **nota de investigación**. Detector de huecos de investigación en el cruce de salud y política (política sanitaria, economía del envejecimiento, geopolítica de la salud: OMS, EMA, FDA, cadenas de suministro farmacéutico).
- Exportación a Markdown, DOCX y PDF.

**CA:** notas con enlaces bidireccionales, repaso espaciado funcional, exportación de ensayos y un vigilante de huecos de investigación con al menos 10 hallazgos semanales enlazados a OpenAlex.

### M13. PRONÓSTICOS
Ver `docs/06_MOTOR_PRONOSTICO.md`.

**Pantalla:**
- Preguntas abiertas y resueltas, con la probabilidad del sistema, la del usuario, la del mercado y la de CAST o una tasa base.
- Tarjeta de cada pregunta con su evolución temporal.
- Curvas de calibración y Brier score del usuario, del sistema, de expertos y de medios.
- Protocolo: el usuario escribe **su** probabilidad **antes** de ver la del sistema.

**CA:** ciclo completo de crear, pronosticar, resolver y puntuar funcionando, con resolución automática cuando exista fuente verificable (dato o resultado).

---

## MODO CEO

### M14. MANDO
**Propósito:** que el mundo se traduzca en decisiones para los negocios del usuario.

**Funciones:**
- **Registro de negocios** (`perfil.yaml` y la UI): empresas, sectores, jurisdicciones, mercados, proveedores clave, divisas y regulación aplicable.
- **Mapa de exposición:** qué eventos tocan qué negocio y por qué canal (regulatorio, fiscal, divisas, cadena de suministro, demanda, reputación). Alertas del tipo: "Evento X afecta a la empresa Y por el canal Z (confianza C)".
- **Radar regulatorio:** diffs de normativa en las jurisdicciones del usuario (UE: IA, datos de salud y EHDS, productos sanitarios, alimentos y complementos alimenticios, consumo; fiscalidad internacional y pilar 2 de la OCDE si aplica; Mónaco, Andorra y España), con plazos de consulta, entrada en vigor y adaptación.
- **Inteligencia de sector:** rondas de financiación, lanzamientos, patentes, ensayos clínicos (ClinicalTrials.gov, EU CTR), fusiones y adquisiciones, y movimientos de talento en los sectores del usuario.
- **Diario de decisiones:** decisión, contexto, premisas explícitas, alternativas descartadas, probabilidad de éxito, pre-mortem ("es dentro de 18 meses y fracasó: ¿por qué?") y fecha de revisión. Se puntúa como un pronóstico.
- **Preparación de reuniones:** a partir de un nombre y una organización (o de un evento de Google Calendar si el usuario lo conecta), un brief de una página con la persona, su organización, su país y sector, lo último que ha dicho y los puntos de interés comunes.
- **Brief ejecutivo** separado del de estudio: riesgos, oportunidades y "qué decidir esta semana".

**CA:**
- Con el perfil de ejemplo, el mapa de exposición detecta al menos 5 eventos pertinentes en una semana real y cada uno explica su canal.
- Diario de decisiones con revisión programada.
- La preparación de reunión se genera en menos de 60 s.

### M15. SIMULADOR
Ver `docs/08_SIMULADOR.md`. Wargames multiactor y simulación de opinión pública para **generar escenarios**, no para predecir.

---

## TRANSVERSALES

### T1. Barra universal y copiloto
Paleta `⌘K` que busca en todo (eventos, actores, países, conceptos, documentos, notas, pronósticos) con búsqueda híbrida. Modo pregunta: el copiloto responde con **citas obligatorias** al archivo de ATLAS y distingue lo que sabe ATLAS de lo que el modelo aporta de conocimiento general. Consultas históricas del tipo "evolución del discurso X entre fechas".

### T2. BRIEF (07:00)
Se entrega a las 07:00 (configurable) en la app, como notificación de macOS y opcionalmente por email.

**Brief de estudio**, unos 10 minutos:
- MUNDO 5, ESPAÑA 5, EUROPA 5, EE. UU. 3, ORIENTE MEDIO 3, ECONOMÍA 5, GEOPOLÍTICA 5, IDEAS 2, CIENCIA/IA/SALUD 3.
- Cada ítem incluye: hechos, divergencia narrativa en una línea, fuente primaria, por qué importa y concepto del grado.
- Cierra con **1 pregunta de pronóstico** para responder y **1 cuestión socrática**.

**Brief ejecutivo:** riesgos, oportunidades, cambios regulatorios y decisiones de la semana.

**Revisión dominical:** pronósticos resueltos, calibración, puntos ciegos de la dieta y lecturas recomendadas del otro lado.

### T3. DIETA — Anti-burbuja
- Registra lo que el usuario abre, lee (tiempo), subraya y guarda.
- Calcula el índice de diversidad en 4 ejes: ideología, región, idioma y tipo de fuente (primaria, datos, académica, opinión).
- **Alertas de punto ciego:** "87% de lo que has leído sobre migración viene de un marco. Aquí tienes los 3 mejores argumentos y datos del otro".
- **Alerta de sesgo de confirmación:** detecta cuándo solo guarda o subraya lo que confirma sus notas previas.
- Todo es transparente y desactivable, y los datos nunca salen de la máquina.

### T4. Alertas
Por umbral de materialidad, por variable de estado, por palabra clave o tema, por actor, por exposición de negocio y por pronóstico cerca de resolverse. Canales: app, notificación de macOS y email. Silencio nocturno configurable.

### T5. SALA DE MÁQUINAS
Panel interno con la salud de cada conector (último éxito, errores, volumen), colas, coste de LLM por día, módulo y modelo, latencias, uso de caché y presupuesto restante. Tiene un botón de pausa por módulo.
