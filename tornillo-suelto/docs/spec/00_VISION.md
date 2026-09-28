# 00 — Visión

## El problema
Estar "hiperinformado" leyendo más no funciona. El volumen de noticias crece y la comprensión no. Los agregadores actuales tienen tres fallos:
1. **Unidad de análisis equivocada.** Trabajan con titulares y artículos, cuando lo que importa son las **afirmaciones** (qué se dice que es verdad) y los **cambios de estado** (qué ha cambiado realmente en el mundo).
2. **El eje izquierda-derecha es un mapa pobre.** El sesgo más distorsionador es la **omisión** (lo que cada ecosistema no cuenta) y, en RR. II., el sesgo **geográfico y lingüístico**: cómo se cuenta lo mismo en Washington, Pekín, Moscú, Doha, Delhi, Ankara o Lagos.
3. **Consumen al usuario en lugar de formarlo.** No miden si entiendes mejor el mundo. La única medida honesta de estar informado es **acertar**: pronósticos calibrados.

## La propuesta
ATLAS es una **terminal personal de inteligencia**. Combina:
- La cobertura de un monitor global.
- El rigor de un servicio de análisis (primaria antes que prensa, trazabilidad total).
- La disciplina de un superpronosticador (probabilidades, calibración, tasas base).
- La profundidad de un seminario de filosofía política (argumentos, tradiciones, lentes teóricas).
- La utilidad de un gabinete de estrategia para un CEO (exposición de sus negocios, radar regulatorio, diario de decisiones).

Todo lo opera una **mesa de agentes**: editor jefe, analistas regionales, macroeconomista, estratega de mercados, analista de conflicto, analista de discurso, filósofo, historiador, estratega corporativo, auditor de evidencia, equipo rojo y superpronosticador. Trabajan sobre un **modelo del mundo** (grafo de conocimiento + variables de estado + canales causales) alimentado por fuentes de todo el planeta.

## Los tres modos
| Modo | Pregunta que responde | Módulos principales |
|---|---|---|
| **ANALISTA** | ¿Qué ha cambiado en el mundo y por qué? | RADAR, EVENTOS, PRISMA, ECONOMÍA, MERCADOS, GEOPOLÍTICA, ACTORES, PRIMARIAS |
| **PENSADOR** | ¿Qué significa, qué tradición lo explica, qué dice la evidencia, qué pienso yo? | ÁGORA (filosofía), ARCHIVO (historia), MEGATENDENCIAS, TALLER (segundo cerebro y producción), PRONÓSTICOS |
| **CEO** | ¿Qué me afecta y qué decido? | MANDO (exposición de negocios, radar regulatorio, diario de decisiones, reuniones), SIMULADOR, Brief ejecutivo |

Una misma noticia se ve distinta en cada modo: como **evento** en Analista, como **problema** en Pensador y como **riesgo u oportunidad** en CEO. El grafo, los datos y los agentes son comunes.

## Principios de producto
1. **Cambios, no titulares.** La pantalla de inicio muestra qué variables de estado del mundo se han movido, ordenadas por **materialidad**, no por viralidad.
2. **Afirmación como átomo.** Todo se descompone en afirmaciones con procedencia, estado e historial de revisiones.
3. **Omisión visible.** Cada evento muestra quién lo cubre, quién no y en qué idiomas.
4. **Primaria primero.** La prensa se usa para interpretar hechos, no para establecerlos.
5. **Probabilidades, no adjetivos.** Cualquier expectativa se convierte en pronóstico registrado y puntuable.
6. **Contra la burbuja.** El sistema detecta los puntos ciegos del usuario y le sirve la mejor versión del argumento contrario (*steelman*), no su caricatura.
7. **Formación, no consumo.** Cada evento enlaza con conceptos del grado (Filosofía Política, Ciencia Política, Economía, RR. II.) y alimenta mapas argumentales, ensayos y repaso espaciado.
8. **Tiempo del usuario como recurso escaso.** El Brief se lee en 10 minutos. La profundidad se elige; nunca se impone.
9. **Memoria histórica total.** Todo se guarda con fecha para poder preguntar dentro de años: "¿cómo evolucionó el discurso europeo sobre migración entre 2026 y 2029?" o "¿qué economistas acertaron sobre Alemania en 2027?".
10. **Honestidad sobre los límites.** Las simulaciones exploran escenarios, no predicen. Los mercados no se "adivinan". Los modelos se equivocan y ATLAS lo mide y lo muestra.

## Usuario
- Estudiante de Filosofía, Política, Economía y RR. II. (modalidad virtual). Asignaturas en curso: Filosofía Política I (Hayek, Shorten, Strauss) y Ciencia Política I: Corrientes e Ideologías (Caminal, Marshall, Savater, Maquiavelo, Hobbes, Montesquieu, Pettit, Kant). Ver `config/perfil.yaml`.
- Científico: fisiología del ejercicio, epidemiología, envejecimiento y salud pediátrica. Publica en revistas indexadas. **Nicho estratégico:** el cruce de política sanitaria, economía del envejecimiento y geopolítica de la salud.
- Empresario con actividad en salud/biotecnología, investigación aplicada, formación y producto digital de salud. Reside en Mónaco y trabaja con Europa, Andorra y otras jurisdicciones. Ver `config/perfil.yaml`.
- Trabaja en español y en inglés. Usa Mac.

## Métricas de éxito (medibles dentro de la app)
- Tiempo diario de lectura: Brief de 10 minutos o menos y profundidad de 45 minutos o menos.
- **Calibración** del usuario (Brier score y curva de calibración) mejorando trimestre a trimestre.
- **Diversidad de dieta informativa**: índice de entropía por ideología, región, idioma y tipo de fuente, con tendencia al alza.
- Porcentaje de afirmaciones en pantalla con fuente primaria enlazada: 70% o más en eventos de Tier 1.
- Ensayos, notas y mapas argumentales producidos al mes.
- Decisiones de empresa registradas con premisas y revisadas.
