# TORNILLO SUELTO · motor ATLAS — comandos (docs/spec CLAUDE.md pide mantenerlos vivos)
PY := .venv/bin/python
ATLAS := .venv/bin/atlas
WEB := apps/web

.PHONY: help install seed ingest markets brief up dev web bundle test lint screenshots clean

help:
	@echo "make install   · crea .venv, instala backend y frontend"
	@echo "make seed      · carga fuentes, países, casos históricos, mapa argumental"
	@echo "make ingest    · una pasada de ingesta real (feeds → eventos → afirmaciones)"
	@echo "make markets   · cinta de mercados y mercados de predicción"
	@echo "make brief     · genera el Brief del día por reglas"
	@echo "make web       · compila el frontend (apps/web/dist)"
	@echo "make bundle    · web + apps/web/web-dist.zip (lo usan instalar-mac.sh y arrancar.sh sin Node)"
	@echo "make up        · levanta todo en http://127.0.0.1:8765 (API + web + planificador)"
	@echo "make dev       · API en 8765 y Vite en 5173 con recarga"
	@echo "make test      · pytest"
	@echo "make lint      · ruff + tsc"

install:
	uv venv .venv && uv pip install --python $(PY) -e ".[dev,extract]"
	cd $(WEB) && npm install

seed:
	$(ATLAS) seed

ingest:
	$(ATLAS) ingest --force

markets:
	$(ATLAS) markets

brief:
	$(ATLAS) brief

web:
	cd $(WEB) && npm run build

bundle: web
	rm -f $(WEB)/web-dist.zip && cd $(WEB)/dist && zip -qr -X ../web-dist.zip .

up: web
	$(ATLAS) serve

dev:
	ATLAS_SCHEDULER=0 $(PY) -m uvicorn atlas_core.api.app:app --app-dir services/core --port 8765 --reload & \
	cd $(WEB) && npm run dev

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check services tests
	cd $(WEB) && npx tsc -b --noEmit

screenshots:
	$(PY) scripts/screenshots.py

clean:
	rm -rf data/atlas.db data/atlas.db-wal data/atlas.db-shm $(WEB)/dist
