"""Capturas de cada pantalla en tema claro y oscuro (verificación visual obligatoria, docs/spec/09).

Uso: python scripts/screenshots.py [--base http://127.0.0.1:8765] [--out docs/capturas]
Requiere el frontend compilado y la API levantada; usa el Chromium preinstalado si existe.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROUTES = [
    ("radar", "/"),
    ("eventos", "/eventos"),
    ("prisma", "/prisma"),
    ("primarias", "/primarias"),
    ("mercados", "/mercados"),
    ("paises", "/paises"),
    ("pais-es", "/paises/ES"),
    ("actores", "/actores"),
    ("agora", "/agora"),
    ("archivo", "/archivo"),
    ("pronosticos", "/pronosticos"),
    ("taller", "/taller"),
    ("mando", "/mando"),
    ("brief", "/brief"),
    ("dieta", "/dieta"),
    ("maquinas", "/maquinas"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    ap.add_argument("--out", default="docs/capturas")
    ap.add_argument("--widths", default="1440")
    args = ap.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright no instalado: pip install -e '.[dev]' && playwright install chromium")
        return 1
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    exe = os.environ.get("CHROMIUM_PATH") or (
        "/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None
    )
    launch = {"executable_path": exe} if exe else {}
    with sync_playwright() as p:
        browser = p.chromium.launch(**launch)
        for width in (int(w) for w in args.widths.split(",")):
            for theme in ("light", "dark"):
                ctx = browser.new_context(
                    viewport={"width": width, "height": 960}, color_scheme=theme, locale="es-ES"
                )
                page = ctx.new_page()
                page.add_init_script(f"try{{localStorage.setItem('ts.theme','{theme}')}}catch(e){{}}")
                for name, route in ROUTES:
                    page.goto(args.base + route, wait_until="networkidle", timeout=60000)
                    page.evaluate(f"document.documentElement.setAttribute('data-theme','{theme}')")
                    page.wait_for_timeout(600)
                    path = out / f"{name}-{theme}-{width}.png"
                    page.screenshot(path=str(path), full_page=False)
                    print("✓", path)
                ctx.close()
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
