"""Aplicación FastAPI: API en /api, frontend compilado en / (SPA) y planificador en proceso."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

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


app = FastAPI(title="TORNILLO SUELTO · motor ATLAS", version=__version__, lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])

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
dist: Path = settings.web_dist
if dist.exists() and (dist / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")
    if (dist / "fonts").exists():
        app.mount("/fonts", StaticFiles(directory=str(dist / "fonts")), name="fonts")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        candidate = dist / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(dist / "index.html"))
else:

    @app.get("/", include_in_schema=False)
    def no_frontend():
        return JSONResponse({"message": "Frontend no compilado. Ejecuta `make web` (o `pnpm --dir apps/web build`). La API está en /api/docs."})
