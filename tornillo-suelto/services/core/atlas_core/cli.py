"""CLI: atlas seed | ingest | markets | brief | serve | stats | verify-feeds."""

from __future__ import annotations

import asyncio
import json

import typer

from .db import get_db
from .settings import settings

app = typer.Typer(help="TORNILLO SUELTO · motor ATLAS", no_args_is_help=True)


@app.command()
def seed() -> None:
    """Carga fuentes, entidades, negocios, variables de estado, casos históricos y el mapa argumental."""
    from .seed import seed_all

    typer.echo(json.dumps(seed_all(get_db()), ensure_ascii=False, indent=2))


@app.command()
def ingest(
    force: bool = typer.Option(False, help="Ignora el intervalo de sondeo"),
    limit: int | None = typer.Option(None, help="Máximo de fuentes"),
    llm: bool = typer.Option(False, help="Usar extractor LLM si hay clave"),
) -> None:
    """Una pasada de ingesta: feeds → documentos → eventos → afirmaciones → materialidad."""
    from .pipeline import run_ingest

    stats = asyncio.run(run_ingest(get_db(), force=force, limit_sources=limit, use_llm=llm or None))
    typer.echo(json.dumps(stats, ensure_ascii=False, indent=2, default=str))


@app.command()
def markets() -> None:
    """Actualiza la cinta de mercados y los mercados de predicción."""
    from .pipeline import run_markets

    typer.echo(json.dumps(asyncio.run(run_markets(get_db())), ensure_ascii=False, indent=2, default=str))


@app.command()
def recompute(hours: int = 72) -> None:
    """Recalcula cobertura y materialidad de los eventos activos."""
    from .pipeline import recompute_events

    typer.echo(json.dumps(recompute_events(get_db(), hours=hours)))


@app.command()
def brief(kind: str = "study", hours: int = 24, redact: bool = False) -> None:
    """Genera el Brief (por reglas; con --redact lo redacta el editor LLM si hay clave)."""
    from .engines.brief import compose_brief

    db = get_db()
    b = compose_brief(db, kind=kind, hours=hours)
    typer.echo(
        f"Brief {b['id']} · {sum(len(s['items']) for s in b['sections'])} ítems en {len(b['sections'])} secciones"
    )
    for s in b["sections"]:
        typer.echo(f"\n## {s['name']}")
        for it in s["items"]:
            typer.echo(f"- [{it['materiality']:.0f}] {it['title']}  ({it['course_concept'] or '—'})")
    typer.echo(
        f"\nPronóstico: {b['forecast_prompt']['title'] if b['forecast_prompt'] else '—'}\nSocrática: {b['socratic_prompt']}"
    )
    if redact:
        from .agents import redact_brief

        typer.echo(json.dumps(redact_brief(db, b["id"]), ensure_ascii=False, indent=2)[:4000])


@app.command()
def serve(host: str = settings.atlas_host, port: int = settings.atlas_port, reload: bool = False) -> None:
    """Arranca la API y la web (http://127.0.0.1:8765)."""
    import uvicorn

    uvicorn.run("atlas_core.api.app:app", host=host, port=port, reload=reload, log_level="info")


@app.command()
def stats() -> None:
    """Resumen de la base de datos."""
    db = get_db()
    out = {
        t: db.scalar(f"SELECT COUNT(*) FROM {t}", (), 0)
        for t in (
            "source",
            "document",
            "event",
            "claim",
            "claim_evidence",
            "state_delta",
            "forecast_question",
            "forecast",
            "prediction_market",
            "market_quote",
            "historical_case",
            "note",
            "llm_call",
            "job_run",
        )
    }
    out["llm_cost_usd_total"] = db.scalar("SELECT COALESCE(SUM(cost_usd),0) FROM llm_call", (), 0)
    typer.echo(json.dumps(out, indent=2))


@app.command(name="verify-feeds")
def verify_feeds() -> None:
    """Comprueba los feeds curados y autodescubre los que faltan (escribe data/feeds_verified.yaml)."""
    import runpy

    runpy.run_path(str(settings.data_dir.parent / "scripts" / "verify_feeds.py"), run_name="__main__")


if __name__ == "__main__":
    app()
