"""Agentes bajo demanda (docs/spec/05 F4): streaming SSE y salidas estructuradas. Sin clave → 409 con estado."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from .. import agents
from ..db import loads
from ..llm import BudgetExceeded, LLMRefused, LLMTruncated, LLMUnavailable, get_llm
from .deps import DaysQ, LimitQ, db

router = APIRouter()
log = logging.getLogger(__name__)


def _status() -> dict[str, Any]:
    llm = get_llm(db())
    st = llm.budget_state()
    st["models"] = {k: v.get("model") for k, v in (llm.cfg.get("tiers") or {}).items()}
    st["message"] = (
        None
        if llm.enabled
        else "Agentes desactivados: añade ANTHROPIC_API_KEY en .env y reinicia. El resto de la herramienta funciona sin clave."
    )
    return st


@router.get("/agents/status")
def status() -> dict[str, Any]:
    return _status()


def _require() -> None:
    llm = get_llm(db())
    if not llm.enabled:
        raise HTTPException(409, _status())
    st = llm.budget_state()
    if st["hard_stop"]:
        raise HTTPException(429, st)


async def _sse(gen: Iterator[dict[str, Any]]):
    loop = asyncio.get_running_loop()
    it = iter(gen)

    def _next():
        try:
            return next(it)
        except StopIteration:
            return None

    while True:
        try:
            item = await loop.run_in_executor(None, _next)
        except Exception as e:  # noqa: BLE001 - las cabeceras 200 ya salieron: avisar con un evento y cerrar
            log.exception("fallo en el stream del agente")
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False),
            }
            break
        if item is None:
            break
        yield {"event": item.get("type", "message"), "data": json.dumps(item, ensure_ascii=False)}


def _stream(fn, *args) -> EventSourceResponse:
    _require()
    try:
        gen = fn(db(), *args)  # event_context() se evalúa aquí, antes de enviar cabeceras: 404 limpio
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    return EventSourceResponse(_sse(gen))


@router.get("/agents/deepen/{event_id}")
async def deepen(event_id: str):
    return _stream(agents.deepen, event_id)


@router.get("/agents/explain/{event_id}")
async def explain(event_id: str):
    return _stream(agents.explain_60s, event_id)


@router.get("/agents/lens")
async def lens(tradition: str, event_id: str | None = None, text: str | None = None):
    return _stream(agents.lens, event_id, tradition, text)


@router.get("/agents/country_changes/{iso2}")
async def country_changes(iso2: str, days: DaysQ = 7):
    return _stream(agents.what_changed_country, iso2.upper(), days)


class SocraticIn(BaseModel):
    mode: str = "socratic"  # socratic | sparring | exam | turing
    message: str
    history: list[dict[str, str]] = Field(default_factory=list)


@router.post("/agents/socratic")
async def socratic(body: SocraticIn):
    history = [
        {"role": h["role"], "content": h["content"]}
        for h in body.history
        if h.get("role") in ("user", "assistant") and h.get("content")
    ]
    return _stream(agents.socratic, body.mode, body.message, history)


def _structured(fn, *args):
    _require()
    try:
        return fn(db(), *args)
    except (LLMUnavailable, BudgetExceeded) as e:
        raise HTTPException(429, str(e)) from e
    except LLMRefused as e:
        raise HTTPException(422, {"message": "El modelo declinó la petición", "detail": str(e)}) from e
    except (LLMTruncated, ValueError) as e:
        raise HTTPException(
            502, {"message": "Salida del modelo cortada o no válida", "detail": str(e)}
        ) from e
    except KeyError as e:
        raise HTTPException(404, str(e)) from e


@router.post("/agents/normative/{event_id}")
def normative(event_id: str) -> dict[str, Any]:
    return _structured(agents.normative_translation, event_id)


@router.post("/agents/red_team/{event_id}")
def red_team(event_id: str) -> dict[str, Any]:
    return _structured(agents.red_team, event_id)


class WhatIfIn(BaseModel):
    event_id: str | None = None
    premise: str


@router.post("/agents/what_if")
def what_if(body: WhatIfIn) -> dict[str, Any]:
    return _structured(agents.what_if, body.event_id, body.premise)


@router.post("/agents/forecast_ensemble/{question_id}")
def ensemble(question_id: str) -> dict[str, Any]:
    return _structured(agents.forecast_ensemble, question_id)


@router.post("/agents/brief_redact/{brief_id}")
def brief_redact(brief_id: str) -> dict[str, Any]:
    return _structured(agents.redact_brief, brief_id)


@router.post("/agents/neutral_title/{event_id}")
def title(event_id: str) -> dict[str, Any]:
    _require()
    return {"title": agents.neutral_title(db(), event_id)}


@router.get("/agents/runs")
def runs(kind: str | None = None, ref: str | None = None, limit: LimitQ = 30) -> dict[str, Any]:
    d = db()
    sql = "SELECT * FROM agent_run WHERE 1=1"
    params: list[Any] = []
    if kind:
        sql += " AND kind = ?"
        params.append(kind)
    if ref:
        sql += " AND ref = ?"
        params.append(ref)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    out = []
    for r in d.all(sql, params):
        x = dict(r)
        x["output"] = loads(x["output"], None)
        out.append(x)
    return {"runs": out}
