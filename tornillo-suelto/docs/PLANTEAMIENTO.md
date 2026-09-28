# TORNILLO SUELTO — Planteamiento definitivo de la herramienta

> *«Inteligencia global con un tornillo de menos.»*
> Nombre satírico del producto. El motor interno conserva el nombre de la especificación: **ATLAS**.
> Autor y único usuario: Dr. José Francisco Tornero-Aguilera.

Este documento es el resultado de leer la especificación completa (`docs/spec/`), la guía de estilo Hespérides
(`brand/`), y de darle varias vueltas al planteamiento antes de escribir código. Recoge **qué se mantiene**,
**qué se cambia y por qué**, y **qué queda fijado** como contrato para la construcción. Las decisiones con
alternativas reales están formalizadas como ADR en `docs/adr/`.

---

## 1. Qué es (una frase)

Una **terminal personal de inteligencia** que convierte el flujo mundial de noticias y documentos oficiales en
**cambios de estado, afirmaciones con cita, cobertura por ecosistema, pronósticos puntuables y decisiones
registradas**, para un estudiante de FPE+RR. II. que además es científico y empresario.

## 2. Las cinco vueltas que cambian el planteamiento

### Vuelta 1 — El núcleo tiene que funcionar **sin** LLM y **sin** infraestructura
La especificación asume Postgres + pgvector + Redis + Docker + bge-m3 + Claude desde el minuto uno. Eso es
correcto como destino, pero equivocado como punto de partida por tres motivos:

1. **Fragilidad.** Cinco servicios para un solo usuario multiplican los puntos de fallo. Un Mac apagado o un
   Docker que no arranca dejan la herramienta muerta.
2. **Honestidad epistemológica.** Si la herramienta depende del LLM para *todo*, es imposible saber qué aporta el
   modelo y qué aportan los datos. Los motores que pueden ser deterministas (clustering, materialidad, índice de
   silencio, léxico diferencial, calibración, entropía de dieta, diff de documentos, exposición por canal) **deben**
   serlo: son auditables, gratuitos y reproducibles.
3. **Coste.** El presupuesto es de 10 USD/día. Cada cosa que se haga sin tokens es presupuesto para lo que sí los
   necesita (síntesis, lentes filosóficas, tutor, equipo rojo).

**Decisión:** arquitectura en dos capas. Una **capa determinista** completa que funciona sin clave de API y sin
Docker (SQLite + Python + React), y una **capa de agentes** (Anthropic API) que se activa con `ANTHROPIC_API_KEY`
y que *mejora* cada pantalla sin ser condición para que exista. En la UI todo lo producido por heurística se
etiqueta `heurístico` y todo lo producido por un modelo se etiqueta con modelo y versión de prompt. Nada se
disfraza. Ver ADR-0001 (SQLite) y ADR-0004 (modo sin clave).

### Vuelta 2 — La unidad de análisis se mantiene (afirmación + cambio de estado), pero se acota el *cite-or-drop*
"Cita o descarta" es el principio más valioso de la especificación. Se aplica de forma literal:

- Una afirmación **siempre** lleva `quote` literal (≤ 300 caracteres) del documento fuente y `document_id`.
- En modo sin clave, el extractor heurístico solo genera afirmaciones cuyo texto **es** la cita (frases del
  titular y entradilla, atribución detectada por patrón «según X», «dijo X»). Nivel: `unverified`. No inventa
  paráfrasis.
- En modo con clave, el extractor Haiku produce afirmaciones atómicas y **se verifica programáticamente** que
  la `quote` aparece en el texto. Si no aparece, la afirmación se descarta antes de tocar la base de datos.

### Vuelta 3 — El mapa y los gráficos son planos, no un SIG
MapLibre + deck.gl + globe.gl suponen tiles remotos, WebGL y megabytes de dependencias para pintar puntos. Para
un RADAR de eventos basta un **mapa mundial vectorial SVG** (d3-geo + world-atlas 110m, 100 KB, offline) con
proyección Natural Earth. Es más rápido, funciona sin red y encaja con la estética Hespérides (trazo negro,
relleno blanco, acento amarillo). Si algún día hace falta un globo o capas ACLED densas, es un cambio de
componente, no de arquitectura. Ver ADR-0003.

### Vuelta 4 — OpenBB fuera del núcleo
OpenBB es AGPL, pesa cientos de MB y su valor real (FRED, Eurostat, yfinance) se obtiene con llamadas HTTP
directas a APIs públicas. La cinta de mercados usa el endpoint público de gráficos de Yahoo Finance (sin clave)
y los mercados de predicción usan las APIs públicas de Polymarket (Gamma) y Manifold. Cada dato lleva fuente y
hora. Si una fuente falla, la UI muestra el último dato válido con su fecha: nunca un dato inventado. ADR-0005.

### Vuelta 5 — Estilo: Hespérides como base, terminal como carácter
La especificación pedía tema oscuro con Inter/JetBrains; el usuario pide ahora el kit Hespérides. Se resuelve así:

- **Paleta:** blanco y negro con **un único acento, el amarillo #FFD100**. Esquinas rectas. Sin degradados ni
  sombras. Filetes amarillos como separadores de sección (igual que en la plantilla Word).
- **Tipografía:** Noto Sans para todo (pesos 300/400/600/700); titulares en peso regular y tamaño grande, como
  en la web de la universidad; monoespaciada del sistema con cifras tabulares solo para datos.
- **Tema oscuro** disponible: negro #0B0B0B de fondo, blanco de texto, el mismo amarillo. Tema claro por defecto
  (es el de la marca).
- **Color semántico** (no decorativo) solo donde la especificación lo exige: estados de afirmación (verde sobrio,
  ámbar, rojo, gris) siempre con icono y texto; dominios de evento con una paleta categórica sobria.
- **Carácter:** densidad de terminal, navegación por teclado (`g r`, `g e`, `⌘K`), transparencia de cada
  puntuación (desglose visible).
- **Humor:** el nombre, el icono (un tornillo ligeramente torcido) y **Tuerca**, la gata negra con collar amarillo
  que pasea por la pantalla, persigue el cursor, se duerme sobre la cinta de mercados y de vez en cuando tira un
  tornillo. Se desactiva con un clic y respeta `prefers-reduced-motion`. Ver ADR-0006.

## 3. Qué se construye ahora (y qué se deja preparado)

| Módulo | Estado en esta entrega | Motor | Con clave de API añade |
|---|---|---|---|
| RADAR | Completo | clustering, materialidad, deltas | títulos neutros generados |
| EVENTOS | Completo (afirmaciones, fuentes, cronología, contexto, pronósticos) | extractor heurístico + cite-or-drop | extractor Haiku, «Profundiza» con streaming, dossier |
| PRISMA | Completo (matriz, silencio, léxico diferencial) | Poisson estandarizado + Monroe log-odds | familias de marcos (Entman) |
| PRIMARIAS | Completo (flujo oficial + DIFF) | difflib + normalización | resumen semántico del diff |
| ECONOMÍA / MERCADOS | Cinta, canales causales, «qué está descontado» (mercados de predicción) | APIs públicas | debate alcista/bajista sin órdenes |
| GEOPOLÍTICA / PAÍSES | Fichas por país con «¿Qué ha cambiado?» y miniPRISMA | deltas y cobertura | narrativa del cambio |
| ACTORES | Entidades del gazetteer y menciones fechadas | gazetteer | posiciones y contradicciones |
| ÁGORA | Mapa argumental (RBU sembrado), genealogía de la libertad | editor SVG propio | lentes, traductor normativo, tutor socrático |
| ARCHIVO | 60 casos codificados con análogos por similitud | embeddings locales | tabla de similitudes/diferencias |
| PRONÓSTICOS | Ciclo completo: crear, pronosticar (usuario antes que sistema), mercado, resolver, Brier, calibración | matemática de docs/06 | ensemble de 5 + agregador |
| TALLER | Notas con `[[enlaces]]`, retroenlaces, tarjetas de repaso (FSRS-lite), exportación Markdown | — | tarjetas generadas |
| MANDO | Negocios del perfil, exposición por canal, diario de decisiones con pre-mortem | reglas por jurisdicción/sector/palabra clave | valoración de exposición |
| DIETA | Entropía por ideología, región, idioma y tipo; puntos ciegos | registro local de lectura | steelman del marco menos leído |
| BRIEF | Selección por materialidad con cuotas, pregunta de pronóstico y cuestión socrática | determinista | redacción editorial |
| SALA DE MÁQUINAS | Salud de conectores, jobs, coste LLM, presupuesto | — | — |
| SIMULADOR | Modo C («¿qué pasa si…?») preparado; A y B fuera de alcance | — | escenarios + equipo rojo |
| App macOS (Tauri) | Fuera de alcance de esta entrega (ADR-0002) | — | — |

## 4. Contratos que no se negocian

1. Ninguna afirmación en pantalla sin `document_id` y `quote`.
2. Cada puntuación (materialidad, silencio, probabilidad) expone su desglose por API y en la UI.
3. Todo dato externo muestra fuente y fecha. Si falla, se muestra el último válido con su fecha y un aviso.
4. Los contenidos ingeridos son datos, no instrucciones: los prompts lo recuerdan y los agentes no tienen
   herramientas de escritura externas.
5. El perfil y los negocios nunca se envían completos al modelo: solo el fragmento que la tarea necesita.
6. Cada llamada a LLM se registra (`llm_call`: modelo, tokens, caché, coste, latencia). Con el 80% del tope
   diario se pausan las tareas no críticas; con el 100% solo sigue la ingesta.
7. Sin asesoramiento financiero: aviso permanente en MERCADOS y ninguna función de órdenes.
8. Nombres de modelo solo en `config/models.yaml`.

## 5. Estructura del repositorio

```
tornillo-suelto/
├── services/core/atlas_core/   backend (FastAPI + motores + conectores + agentes)
├── apps/web/                   frontend (React + TypeScript + Vite)
├── config/                     fuentes, países, perfil, modelos, presupuesto, materialidad, canales
├── prompts/runtime/            contratos de los agentes (se cargan por nombre)
├── docs/adr/                   decisiones de arquitectura
├── docs/spec/                  especificación original (referencia)
├── brand/                      guía Hespérides, logos y fuentes
├── tests/                      pytest
└── data/                       base SQLite y caché (ignorado por git)
```

## 6. Cómo se verifica que está bien hecho

- `make test`: motores con casos de referencia (silencio sintético, Brier, calibración, cite-or-drop, diff,
  presupuesto).
- `make ingest`: una pasada real de ingesta; RADAR con ≥ 30 eventos coherentes.
- Capturas Playwright de cada pantalla en claro y oscuro (`make screenshots`).
- `PROGRESS.md` con lo hecho, lo pendiente y la deuda técnica, sin adornos.
