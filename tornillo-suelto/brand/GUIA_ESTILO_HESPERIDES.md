# Guía de estilo · Trabajos para la Universidad de las Hespérides (.h)

**Autor de todos los trabajos:** Dr. José Francisco Tornero-Aguilera
**Grado:** Doble Grado en Filosofía, Política y Economía + Relaciones Internacionales (modalidad online)
**Fuente de los datos:** CSS y recursos públicos de hesperides.edu.es, extraídos el 26-09-2026. La universidad no publica un manual de marca ni una plantilla oficial para trabajos de alumnos, así que esta guía reproduce su identidad web.

---

## 1. Identidad visual (extraída de la web)

### Tipografía
| Uso | Fuente | Detalle en la web |
|---|---|---|
| Todo el sitio (titulares y texto) | **Noto Sans HK** (Google Fonts) | pesos 300 / 400 / 700 |
| Avisos y elementos secundarios | **Noto Sans** (Google Fonts) | la misma familia, versión latina |

En la parte latina, Noto Sans HK y Noto Sans usan los **mismos glifos**. Para Word se usa **Noto Sans**: es gratuita y está incluida en `fuentes/`. Si el ordenador no la tiene, Word la sustituye por Arial o Calibri.

Estilo tipográfico del sitio: titulares **en peso regular (400), no negrita**, con tamaño grande y en casi negro. La negrita se reserva a subtítulos pequeños (h4 = 600–700).

| Nivel web | Tamaño | Peso | Color |
|---|---|---|---|
| H1 | 40 px | 400 | #0B0B0B |
| H2 | 27–36 px | 400 | #0B0B0B |
| H4 | 21 px | 600–700 | #0B0B0B |
| Texto | 18 px / interlineado 1,5 | 400 | #1D1D1D |
| Botones | 13 px | 400 | blanco sobre negro, esquinas rectas (0 px) |

### Paleta
| Token | HEX | RGB | Uso en la web |
|---|---|---|---|
| **Amarillo .h** | **#FFD100** | 255, 209, 0 | Color de marca: cabecera, bloques destacados, subrayados de cifras y titulares |
| Amarillo alt. | #FCD101 / #FFCD00 | — | Variantes del mismo amarillo (botones de búsqueda) |
| Negro | #000000 | 0, 0, 0 | Botones, logotipo, pie |
| Titulares | #0B0B0B | 11, 11, 11 | Encabezados |
| Texto | #1D1D1D | 29, 29, 29 | Cuerpo |
| Gris medio | #757575 | 117, 117, 117 | Texto secundario, metadatos |
| Gris claro | #E6E6E6 | 230, 230, 230 | Separadores |
| Fondo suave | #F7F7F7 | 247, 247, 247 | Cajas |
| Azul acento | #2B7BB9 | 43, 123, 185 | Enlaces |
| Rojo aviso | #BD382F | 189, 56, 47 | Banner de avisos (solo alertas) |

**Regla de uso:** base blanco y negro, con el amarillo como único color de acento. Nada de degradados ni sombras. Esquinas rectas.

### Logotipo
- `logos/logo_h_negro.png`: «.h universidad de las hespérides online» en negro con fondo transparente (731 × 192 px). Para fondos blancos o amarillos.
- `logos/logo_h_blanco.png`: la misma versión en blanco. Para fondos negros.
- Marca abreviada: **.h** (la propia universidad se llama así: «Campus .h», «Modelo educativo .h»).
- Lema: *«Libre de aprender a ser libre.»*

> Nota: el logo es de la universidad. Se usa en la portada para identificar el centro, igual que hace cualquier alumno. No es un documento oficial de la institución.

---

## 2. Formato de los trabajos (plantilla Word)

| Elemento | Especificación |
|---|---|
| Papel | A4, márgenes de 2,5 cm |
| Fuente | Noto Sans |
| Cuerpo | 11 pt, justificado, interlineado 1,3, 8 pt tras cada párrafo, color #1D1D1D |
| Título 1 | 18 pt regular, filete amarillo #FFD100 debajo |
| Título 2 | 13 pt negrita |
| Título 3 | 11 pt negrita cursiva |
| Referencias | 10 pt, sangría francesa de 1,25 cm, APA 7.ª ed. |
| Pies de figura | 9 pt gris, «**Figura N.** Descripción.» |
| Cabecera | Logo .h pequeño a la izquierda; «Asignatura · Práctica N» a la derecha; filete amarillo |
| Pie de página | «Dr. José Francisco Tornero-Aguilera» a la izquierda; «página / total» a la derecha |
| Cajas destacadas | Fondo #F7F7F7 con filete amarillo grueso a la izquierda |
| Viñetas | Guion (–), sin puntos gruesos |

### Portada (sin cabecera ni pie)
1. Logo .h
2. GRADO (versalitas grises) · Asignatura · Curso
3. Barra amarilla gruesa
4. PRÁCTICA N.º (negrita) · **Título** (28 pt regular)
5. Autor: **Dr. José Francisco Tornero-Aguilera** · Docente · Fecha de entrega

### Estructura estándar de una práctica
1. Resumen + palabras clave
2. Introducción (pregunta, tesis y estructura)
3. Marco conceptual (autores y conceptos)
4. Desarrollo / análisis (argumento propio)
5. Conclusiones
6. Referencias (APA 7)
7. **Anexo I. Registro manuscrito**: fotografía del trabajo hecho a mano, con pie «Figura A1. Borrador manuscrito de la práctica. Fotografía del autor, [fecha].»

Si el enunciado de una práctica exige otra estructura, manda el enunciado.

---

## 3. Normas fijas
- **Firma siempre:** Dr. José Francisco Tornero-Aguilera (con guion entre los apellidos).
- **Anexo manuscrito obligatorio** en cada práctica, como constancia de autoría.
- Citas en APA 7.ª ed., salvo que el docente pida otro sistema.
- Nombre de archivo para subir: `Tornero-Aguilera_JF_[Asignatura]_Practica[N].docx` (o `.pdf`).

---

## 4. Cómo generar una práctica nueva
En `plantillas/build_plantilla.js`, rellenar el bloque `C` (asignatura, número, título, docente y fecha) y ejecutar:
```
node build_plantilla.js Tornero-Aguilera_JF_[Asignatura]_Practica[N].docx
```
También se puede abrir `Plantilla_Trabajo_Hesperides.docx` en Word y sustituir los campos entre [corchetes]. Los estilos «Cuerpo», «Referencia», «Pie de figura» y «Título 1-3» ya están definidos.
