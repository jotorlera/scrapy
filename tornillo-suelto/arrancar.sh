#!/usr/bin/env bash
# TORNILLO SUELTO · arranque en un comando (macOS / Linux).
#   ./arrancar.sh            instala, siembra, ingesta unas fuentes y abre http://127.0.0.1:8765
#   ./arrancar.sh --rapido   salta la ingesta inicial (solo semillas); el planificador ingesta en segundo plano
#   ./arrancar.sh --solo-instalar   instala y compila, sin arrancar
# Requisitos: Python ≥ 3.11 y Node ≥ 20 en el PATH. Todo lo demás se instala en ./.venv y apps/web/node_modules.
set -euo pipefail
cd "$(dirname "$0")"

RAPIDO=0; SOLO_INSTALAR=0
for a in "$@"; do
  case "$a" in
    --rapido) RAPIDO=1 ;;
    --solo-instalar) SOLO_INSTALAR=1 ;;
    *) echo "opción desconocida: $a"; exit 2 ;;
  esac
done

paso() { printf '\n\033[1;33m▶ %s\033[0m\n' "$*"; }
fallo() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }

# 1. Python
PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PY="$(command -v "$c")"; break
  fi
done
[ -n "$PY" ] || fallo "Hace falta Python 3.11 o superior (https://www.python.org/downloads/ o 'brew install python')."
command -v node >/dev/null 2>&1 || fallo "Hace falta Node 20 o superior (https://nodejs.org o 'brew install node')."
node -e 'process.exit(parseInt(process.versions.node) >= 20 ? 0 : 1)' || fallo "Node demasiado antiguo: hace falta la versión 20 o superior."

# 2. Entorno Python
paso "Entorno Python en .venv ($("$PY" --version))"
if [ ! -x .venv/bin/python ]; then
  if command -v uv >/dev/null 2>&1; then uv venv .venv --python "$PY" >/dev/null; else "$PY" -m venv .venv; fi
fi
if command -v uv >/dev/null 2>&1; then
  uv pip install --python .venv/bin/python -q -e ".[extract]"
else
  .venv/bin/python -m pip install -q --upgrade pip
  .venv/bin/python -m pip install -q -e ".[extract]"
fi

# 3. Frontend
paso "Frontend (npm install + build)"
( cd apps/web && npm install --no-audit --no-fund --silent && npm run build --silent )

# 4. Configuración
[ -f .env ] || cp .env.example .env
[ -f config/perfil.yaml ] || { cp config/perfil.example.yaml config/perfil.yaml; echo "config/perfil.yaml creado desde la plantilla (edítalo con tus estudios y negocios; no se sube a git)."; }
mkdir -p data

# 5. Datos
paso "Semillas (fuentes, países, casos históricos, mapa argumental)"
.venv/bin/atlas seed
if [ "$RAPIDO" = 0 ]; then
  paso "Ingesta inicial (40 fuentes; el resto las cubre el planificador en segundo plano)"
  .venv/bin/atlas ingest --force --limit 40 || echo "La ingesta inicial falló o no hay red: la herramienta arranca igual y reintenta en segundo plano."
  .venv/bin/atlas markets || true
  .venv/bin/atlas brief || true
fi
.venv/bin/atlas stats || true

[ "$SOLO_INSTALAR" = 1 ] && { echo; echo "Instalado. Arranca con: .venv/bin/atlas serve   (o ./arrancar.sh)"; exit 0; }

# 6. Servir y abrir el navegador
URL="http://127.0.0.1:8765"
paso "Sirviendo en $URL  (Ctrl+C para parar)"
( sleep 2; command -v open >/dev/null 2>&1 && open "$URL" || { command -v xdg-open >/dev/null 2>&1 && xdg-open "$URL" || true; } ) &
exec .venv/bin/atlas serve
