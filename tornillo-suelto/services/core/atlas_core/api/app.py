"""Aplicación FastAPI: API en /api, frontend compilado en / (SPA) y planificador en proceso."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from .. import __version__
from ..db import get_db
from ..llm import get_llm
from ..scheduler import Scheduler
from ..settings import settings
from .routes_agents import router as agents_router
from .routes_analyst import router as analyst_router
from .routes_ceo import router as ceo_router
from .routes_thinker import router as thinker_router

scheduler: Scheduler | None = None

# ---- defensa frente al navegador del propio usuario ----
# La API solo escucha en 127.0.0.1, pero cualquier página web abierta en el mismo equipo puede pedirle cosas:
# un <img src=".../api/agents/deepen/x"> o un <form method=post> se envían sin preflight (CSRF) y CORS solo
# impide *leer* la respuesta, no el efecto. Con DNS rebinding la página pasa además a ser same-origin.
# Dos comprobaciones: (1) Host debe ser local (TrustedHostMiddleware, corta el rebinding y protege también
# las lecturas: perfil, notas, decisiones); (2) toda petición con efectos bajo /api (métodos no seguros y los
# agentes SSE, que son GET con coste) debe venir del mismo origen o de una navegación directa.
# Sin cabeceras de navegador (curl, tests, CLI) se permite. ATLAS_ALLOWED_HOSTS (coma) añade hosts, p. ej. Tailscale.
LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]")
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


def allowed_hosts() -> list[str]:
    extra = getattr(settings, "atlas_allowed_hosts", "") or ""
    return [*LOCAL_HOSTS, *[h.strip() for h in str(extra).split(",") if h.strip()]]


def _has_side_effects(method: str, path: str) -> bool:
    if not path.startswith("/api/"):
        return False
    return method not in SAFE_METHODS or path.startswith("/api/agents/")


def cross_site_reason(headers: Headers) -> str | None:
    """Motivo del rechazo si la petición la lanzó otro sitio desde un navegador; None si es legítima."""
    site = headers.get("sec-fetch-site")
    if site is not None:
        # same-origin: la SPA (o el proxy de Vite); none: navegación directa / barra de direcciones.
        return None if site in ("same-origin", "none") else f"Sec-Fetch-Site: {site}"
    origin = headers.get("origin")
    if origin:
        # navegadores sin Sec-Fetch-*: en un POST cross-site siempre envían Origin
        host = (urlsplit(origin).hostname or "").lower()
        if host and ":" in host:
            host = f"[{host}]"
        if host not in {h.lower() for h in allowed_hosts()}:
            return f"Origin: {origin}"
    return None


class CrossSiteGuard:
    """Middleware ASGI puro (no BaseHTTPMiddleware: no interfiere con los streams SSE)."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and _has_side_effects(scope["method"], scope["path"]):
            reason = cross_site_reason(Headers(scope=scope))
            if reason:
                response = JSONResponse(
                    {
                        "detail": f"Petición cross-site rechazada ({reason}). ATLAS solo atiende a su propia interfaz."
                    },
                    status_code=403,
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    db = get_db()
    _ = db.conn  # inicializa esquema
    if settings.atlas_scheduler:
        scheduler = Scheduler(db)
        task = asyncio.create_task(scheduler.run())
    else:
        task = None
    yield
    if scheduler:
        scheduler.stop()
    if task:
        task.cancel()


app = FastAPI(
    title="TORNILLO SUELTO · motor ATLAS",
    version=__version__,
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
# Sin CORSMiddleware: en desarrollo Vite hace proxy de /api (mismo origen) y en producción la SPA se sirve desde
# aquí; una lista blanca de orígenes solo daría lectura y escritura a cualquier página servida en ese puerto.
app.add_middleware(CrossSiteGuard)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts())

app.include_router(analyst_router, prefix="/api", tags=["analista"])
app.include_router(thinker_router, prefix="/api", tags=["pensador"])
app.include_router(ceo_router, prefix="/api", tags=["ceo"])
app.include_router(agents_router, prefix="/api", tags=["agentes"])


@app.get("/api/health")
def health() -> dict[str, Any]:
    db = get_db()
    llm = get_llm(db)
    return {
        "status": "ok",
        "name": "TORNILLO SUELTO",
        "engine": "ATLAS",
        "version": __version__,
        "llm_enabled": llm.enabled,
        "db_path": str(db.path),
        "scheduler": bool(scheduler and scheduler.running),
        "counts": {
            "sources": db.scalar("SELECT COUNT(*) FROM source WHERE active = 1", (), 0),
            "documents": db.scalar("SELECT COUNT(*) FROM document", (), 0),
            "events": db.scalar("SELECT COUNT(*) FROM event", (), 0),
            "claims": db.scalar("SELECT COUNT(*) FROM claim", (), 0),
        },
        "tagline": "Inteligencia global con un tornillo de menos.",
    }


# ---- frontend estático (SPA) ----


def mount_frontend(app: FastAPI, dist: Path) -> None:
    """Sirve la SPA compilada en `/`; sin `dist`, un aviso JSON. Nunca eclipsa /api ni sale de `dist`."""
    if not (dist / "index.html").exists():

        @app.get("/", include_in_schema=False)
        def no_frontend():
            return JSONResponse(
                {
                    "message": "Frontend no compilado. Ejecuta `make web` (o `pnpm --dir apps/web build`). La API está en /api/docs."
                }
            )

        return

    base = dist.resolve()
    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")
    if (dist / "fonts").exists():
        app.mount("/fonts", StaticFiles(directory=str(dist / "fonts")), name="fonts")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        # La API vive bajo /api: una ruta desconocida ahí es un 404 JSON, nunca el index.html de la SPA.
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="ruta de API no encontrada")
        # Rutas absolutas y `..` (el SO sí los colapsa aunque pathlib no) se rechazan antes de tocar disco.
        if full_path.startswith("/") or ".." in Path(full_path).parts:
            raise HTTPException(status_code=404, detail="ruta no válida")
        candidate = (base / full_path).resolve()
        if full_path and candidate.is_relative_to(base) and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(base / "index.html"))


mount_frontend(app, settings.web_dist)
