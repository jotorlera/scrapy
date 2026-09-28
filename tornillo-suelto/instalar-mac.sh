#!/usr/bin/env bash
# TORNILLO SUELTO · instalador para macOS (también funciona en Linux).
#
#   curl -fsSL https://raw.githubusercontent.com/jotorlera/scrapy/claude/cloud-tool-cat-feature-dtnbrj/tornillo-suelto/instalar-mac.sh | bash
#
# No necesita Python, Node, git, Homebrew ni Xcode: descarga el código como zip, instala `uv`, que a su vez
# instala un Python propio dentro de la carpeta, usa la web ya compilada (apps/web/web-dist.zip), siembra la base
# de datos, hace una primera ingesta y deja en ~/Applications «TORNILLO SUELTO.app» para abrirlo con doble clic.
#
# Variables opcionales: TS_DIR (carpeta destino, por defecto ~/TornilloSuelto), TS_SOURCE_DIR (usar una copia local
# en vez de descargar), TS_SIN_INGESTA=1 (saltar la ingesta inicial), TS_SIN_ABRIR=1 (no abrir el navegador al final).
set -euo pipefail

BRANCH="claude/cloud-tool-cat-feature-dtnbrj"
ZIP_URL="https://codeload.github.com/jotorlera/scrapy/zip/refs/heads/${BRANCH}"
DEST="${TS_DIR:-$HOME/TornilloSuelto}"
PYVER="3.12"
URL="http://127.0.0.1:8765"

paso() { printf '\n\033[1;33m▶ %s\033[0m\n' "$*"; }
fallo() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }

case "$(uname -s)" in Darwin|Linux) ;; *) fallo "Este instalador es para macOS o Linux. En Windows usa WSL." ;; esac
command -v curl >/dev/null 2>&1 || fallo "Falta curl (viene con macOS)."

# 1. Código fuente (conserva .venv, data, .env y perfil.yaml de una instalación anterior; sin rsync)
instalar_src() {  # $1 = carpeta con el código nuevo
  local nuevo="$DEST/src.nuevo" viejo="$DEST/src"
  rm -rf "$nuevo"; mkdir -p "$nuevo"
  (cd "$1" && tar --exclude=.venv --exclude=data --exclude=node_modules --exclude=.env --exclude=config/perfil.yaml -cf - .) | (cd "$nuevo" && tar -xf -)
  if [ -d "$viejo" ]; then
    for k in .venv data .env config/perfil.yaml; do [ -e "$viejo/$k" ] && mv "$viejo/$k" "$nuevo/$k"; done
    rm -rf "$DEST/src.anterior"; mv "$viejo" "$DEST/src.anterior"
  fi
  mv "$nuevo" "$viejo"; rm -rf "$DEST/src.anterior"
}
paso "Código en $DEST"
mkdir -p "$DEST"
if [ -n "${TS_SOURCE_DIR:-}" ]; then
  instalar_src "$TS_SOURCE_DIR"
else
  TMP="$(mktemp -d)"
  curl -fL --progress-bar -o "$TMP/src.zip" "$ZIP_URL" || fallo "No se pudo descargar el código ($ZIP_URL)."
  (cd "$TMP" && unzip -q src.zip)
  SRC_IN_ZIP="$(find "$TMP" -maxdepth 2 -type d -name tornillo-suelto | head -1)"
  [ -n "$SRC_IN_ZIP" ] || fallo "El zip descargado no contiene tornillo-suelto/."
  instalar_src "$SRC_IN_ZIP"
  rm -rf "$TMP"
fi
SRC="$DEST/src"
cd "$SRC"

# 2. uv + Python propio (sin tocar el sistema)
paso "Gestor uv y Python $PYVER (privados de la instalación)"
export UV_INSTALL_DIR="$DEST/bin" UV_PYTHON_INSTALL_DIR="$DEST/python" UV_CACHE_DIR="$DEST/cache"
UV="$DEST/bin/uv"
if [ ! -x "$UV" ]; then
  curl -fsSL https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$DEST/bin" UV_NO_MODIFY_PATH=1 sh >/dev/null || fallo "No se pudo instalar uv."
fi
"$UV" python install "$PYVER" >/dev/null 2>&1 || "$UV" python install "$PYVER"
[ -x .venv/bin/python ] || "$UV" venv .venv --python "$PYVER" >/dev/null
"$UV" pip install --python .venv/bin/python -q -e ".[extract]" || fallo "Falló la instalación de dependencias Python."

# 3. Web compilada
paso "Interfaz web"
if command -v node >/dev/null 2>&1 && [ -d apps/web/node_modules ]; then
  (cd apps/web && npm run build --silent) || true
fi
if [ ! -f apps/web/dist/index.html ]; then
  rm -rf apps/web/dist && mkdir -p apps/web/dist && (cd apps/web/dist && unzip -qo ../web-dist.zip)
fi
[ -f apps/web/dist/index.html ] || fallo "No hay interfaz web (falta apps/web/web-dist.zip)."

# 4. Configuración y datos
[ -f .env ] || cp .env.example .env
[ -f config/perfil.yaml ] || cp config/perfil.example.yaml config/perfil.yaml
mkdir -p data
paso "Semillas (301 fuentes, países, casos históricos, mapa argumental)"
.venv/bin/atlas seed >/dev/null
if [ "${TS_SIN_INGESTA:-0}" != 1 ]; then
  paso "Primera ingesta (40 fuentes; el planificador sigue con el resto en segundo plano)"
  .venv/bin/atlas ingest --force --limit 40 >/dev/null 2>&1 || echo "  (sin red o feeds caídos: la herramienta arranca igual y reintenta sola)"
  .venv/bin/atlas markets >/dev/null 2>&1 || true
  .venv/bin/atlas brief >/dev/null 2>&1 || true
fi

# 5. Lanzadores
paso "Lanzadores"
cat > "$DEST/tornillo-suelto" <<LAUNCH
#!/usr/bin/env bash
# Arranca TORNILLO SUELTO (si no está ya en marcha) y abre el navegador. Uso: tornillo-suelto [start|stop|status|log]
SRC="$SRC"; URL="$URL"; PIDF="\$SRC/data/server.pid"; LOG="\$SRC/data/server.log"
abrir() { command -v open >/dev/null 2>&1 && open "\$URL" || { command -v xdg-open >/dev/null 2>&1 && xdg-open "\$URL" || echo "Abre \$URL"; }; }
vivo() { curl -sf "\$URL/api/health" 2>/dev/null | grep -q '"TORNILLO SUELTO"'; }
case "\${1:-start}" in
  stop)
    PIDS="\$( { [ -f "\$PIDF" ] && cat "\$PIDF"; pgrep -f "\$SRC/.venv/bin/python .*atlas serve"; } 2>/dev/null | sort -u )"
    if [ -n "\$PIDS" ]; then kill \$PIDS 2>/dev/null; sleep 1; echo "Parado."; else echo "No estaba en marcha."; fi
    rm -f "\$PIDF" ;;
  status) vivo && echo "En marcha en \$URL" || echo "Parado" ;;
  log)    tail -n 50 -f "\$LOG" ;;
  start)
    if ! vivo; then
      cd "\$SRC" || exit 1
      nohup .venv/bin/atlas serve >> "\$LOG" 2>&1 < /dev/null &
      echo \$! > "\$PIDF"
      for i in \$(seq 1 30); do vivo && break; sleep 1; done
      vivo || { echo "No arrancó. Últimas líneas del registro:"; tail -n 20 "\$LOG"; exit 1; }
    fi
    [ "\${TS_SIN_ABRIR:-0}" = 1 ] || abrir
    echo "TORNILLO SUELTO en \$URL  ·  parar: \$0 stop" ;;
  *) echo "uso: \$0 [start|stop|status|log]"; exit 2 ;;
esac
LAUNCH
chmod +x "$DEST/tornillo-suelto"

if [ "$(uname -s)" = Darwin ]; then
  APP="$HOME/Applications/TORNILLO SUELTO.app"
  mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
  cat > "$APP/Contents/MacOS/tornillo" <<APP
#!/usr/bin/env bash
exec "$DEST/tornillo-suelto" start
APP
  chmod +x "$APP/Contents/MacOS/tornillo"
  cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>TORNILLO SUELTO</string>
  <key>CFBundleDisplayName</key><string>TORNILLO SUELTO</string>
  <key>CFBundleIdentifier</key><string>es.tornero.tornillosuelto</string>
  <key>CFBundleVersion</key><string>0.1.0</string>
  <key>CFBundleShortVersionString</key><string>0.1.0</string>
  <key>CFBundleExecutable</key><string>tornillo</string>
  <key>CFBundleIconFile</key><string>tornillo</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSUIElement</key><true/>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
</dict></plist>
PLIST
  # Icono desde el favicon SVG (qlmanage + sips + iconutil vienen con macOS); si falla, sin icono.
  ( set +e; T="$(mktemp -d)"; qlmanage -t -s 1024 -o "$T" apps/web/public/favicon.svg >/dev/null 2>&1
    PNG="$(ls "$T"/*.png 2>/dev/null | head -1)"
    if [ -n "$PNG" ]; then
      mkdir -p "$T/i.iconset"
      for s in 16 32 128 256 512; do
        sips -z $s $s "$PNG" --out "$T/i.iconset/icon_${s}x${s}.png" >/dev/null 2>&1
        sips -z $((s*2)) $((s*2)) "$PNG" --out "$T/i.iconset/icon_${s}x${s}@2x.png" >/dev/null 2>&1
      done
      iconutil -c icns "$T/i.iconset" -o "$APP/Contents/Resources/tornillo.icns" >/dev/null 2>&1
    fi; rm -rf "$T" ) || true
  touch "$APP"
  echo "  · $APP  (doble clic para abrir)"
fi
echo "  · $DEST/tornillo-suelto start|stop|status|log  (desde Terminal)"

# 6. Arrancar
paso "Listo"
.venv/bin/atlas stats 2>/dev/null | grep -E '"(document|event|claim|prediction_market)"' | sed 's/^/  /' || true
echo
echo "Perfil personal (estudios y negocios para MANDO): $SRC/config/perfil.yaml  → después, $DEST/tornillo-suelto stop && cd $SRC && .venv/bin/atlas seed"
echo "Agentes con IA (opcional): añade ANTHROPIC_API_KEY en $SRC/.env y reinicia."
echo
"$DEST/tornillo-suelto" start
