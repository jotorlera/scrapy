# ADR-0003 — Mapa SVG (d3-geo) y embeddings locales por niveles

**Estado:** aceptada · 2026-09-28

## Mapa
**Contexto.** MapLibre + deck.gl + globe.gl exigen WebGL, tiles remotos y varios MB. El RADAR necesita puntos por
evento con tamaño y color, clic por país y ninguna capa raster.
**Decisión.** Mapa mundial vectorial con `d3-geo` + `world-atlas` (110 m, TopoJSON, ~100 KB), proyección Natural
Earth, renderizado SVG. Offline, plano, coherente con el estilo (trazo negro, relleno blanco, acento amarillo).
**Consecuencias.** Sin zoom continuo ni tiles; si hiciera falta una capa densa (ACLED), se evaluará canvas o
MapLibre en un ADR posterior.

## Embeddings
**Contexto.** `BAAI/bge-m3` (≈ 2,3 GB) da la mejor agrupación multilingüe, pero descargarlo no siempre es posible
y en muchos casos no hace falta para agrupar titulares del mismo día.
**Decisión.** Interfaz `Embedder` con dos implementaciones:
- `HashingEmbedder` (por defecto): n-gramas de caracteres (3-5) y palabras, *hashing trick* a 1024 dimensiones,
  normalización L2. Sin descarga, determinista, razonable entre idiomas próximos.
- `SentenceTransformerEmbedder` (`ATLAS_EMBEDDINGS=bge-m3`): bge-m3 local si está instalado
  (`pip install -e ".[embeddings]"`).
La dimensión es fija (1024) en ambas; los vectores de espacios distintos nunca se mezclan (columna
`embedding_model` en cada tabla con vectores).
**Consecuencias.** El clustering exige además coincidencia de al menos una entidad principal (país, institución,
actor del gazetteer) y coherencia temporal, lo que compensa la menor calidad del embedder por defecto.
