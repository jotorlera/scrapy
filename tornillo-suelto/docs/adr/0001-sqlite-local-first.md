# ADR-0001 — SQLite en lugar de Postgres + pgvector + Redis

**Estado:** aceptada · 2026-09-28

## Contexto
La especificación propone PostgreSQL 16 + pgvector + pg_trgm, Redis para colas (arq) y DuckDB/Parquet para
series. El entorno de construcción no tiene Docker ni un servidor Postgres, y el producto es para **un** usuario en
**un** Mac. El volumen previsto (decenas de miles de documentos al mes, cientos de eventos al día) está muy por
debajo de lo que justifica un servidor de base de datos.

## Opciones
1. Postgres + Redis con docker compose (según especificación).
2. **SQLite** (WAL, FTS5) con vectores en BLOB y búsqueda por fuerza bruta con NumPy; planificador asyncio en el
   mismo proceso.
3. DuckDB como base principal.

## Decisión
Opción 2. Un solo archivo `data/atlas.db`, cero instalación, copia de seguridad = copiar un archivo, y el mismo
código corre en el contenedor de desarrollo y en el Mac. La capa de acceso a datos está aislada en
`atlas_core/db.py`; el esquema conserva los nombres y las relaciones del `schema.sql` de referencia para que una
migración futura a Postgres sea mecánica.

## Consecuencias
- Búsqueda vectorial O(n) sobre centroides de eventos activos (cientos) y sobre documentos recientes (miles): sin
  problema medido; si crece, se añade un índice (sqlite-vec o Postgres) sin tocar los motores.
- Sin Redis: las tareas periódicas corren en un bucle asyncio dentro del proceso de la API (`scheduler.py`).
  Es suficiente para un usuario; la ingesta no bloquea la API porque las llamadas de red son asíncronas.
- Las series temporales pequeñas (cinta de mercados, mercados de predicción) van a tablas normales; no hace falta
  Parquet en esta fase.
