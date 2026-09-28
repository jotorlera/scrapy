# ADR-0006 — Nombre, estilo visual y la gata Tuerca

**Estado:** aceptada · 2026-09-28

## Nombre
El usuario pide un nombre satírico relacionado con el apellido Tornero. Candidatos: *Tornoscopio*, *Tornavueltas*,
*Tornocracia*, *El Torno del Mundo*, *Tornillo Suelto*. Se elige **TORNILLO SUELTO** («tener un tornillo suelto»
= estar un poco loco): autoparodia, memorable, y da un icono obvio (un tornillo ligeramente torcido) en el amarillo
de la marca. Lema: *«Inteligencia global con un tornillo de menos.»* El motor conserva el nombre técnico ATLAS.

## Estilo
Base: kit Hespérides (`brand/GUIA_ESTILO_HESPERIDES.md`). Tokens en `apps/web/src/styles/tokens.css`:
amarillo #FFD100, negro #000, titulares #0B0B0B, texto #1D1D1D, gris #757575, separadores #E6E6E6, fondo suave
#F7F7F7, enlace #2B7BB9, aviso #BD382F. Noto Sans (fuentes locales del kit, servidas por la app; sin llamadas a
Google Fonts). Esquinas rectas, sin sombras ni degradados. Tema oscuro: mismos tokens invertidos con el mismo
amarillo. El logotipo de la universidad **no** se usa en la app: es una herramienta personal, no un documento
académico. Se usa en las plantillas de exportación de trabajos (TALLER), como hace cualquier alumno.

## La gata
Referencia encontrada en GitHub: **oneko.js** (adryd325/oneko.js, MIT): el gato que persigue el cursor, con
sprites del Neko clásico. Se toma el patrón (bucle de 100 ms, estados idle/alert/run/sleep/scratch, seguimiento
del cursor con umbral) pero **no los sprites**, cuya autoría original es ajena y no encaja en blanco/negro/amarillo.
Se dibuja una gata propia en SVG animado por CSS: **Tuerca**, negra, con collar amarillo, que:
- sigue al cursor cuando se aleja, con animación de andar;
- se sienta y se lame cuando el cursor se queda quieto;
- se duerme sobre la cinta de mercados si pasan más de 2 minutos sin actividad;
- de vez en cuando persigue un tornillo amarillo que rueda por la pantalla y lo tira fuera de ella;
- ronronea (texto «prrr») al pasar el ratón por encima y se aparta si tapa algo (clic la manda a la esquina).
Se desactiva desde Ajustes y con `prefers-reduced-motion`. Nunca intercepta clics de la interfaz (`pointer-events`
solo en su propio cuerpo).
