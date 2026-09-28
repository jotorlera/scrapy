"""Agentes runtime (docs/spec/05). Cada uno carga su contrato de prompts/runtime/<agente>.md por nombre, recibe
solo el contexto mínimo (nunca el perfil completo) y devuelve una salida validada o un stream.

Todo el contenido de documentos que se pasa al modelo va dentro de etiquetas <documento> y el preámbulo común
recuerda que es material de análisis, no instrucciones.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel, Field

from .config_loader import profile_config
from .db import Database, dumps, loads, new_id, now_iso
from .engines import forecast as fmath
from .engines.claims import ClaimCandidate, claims_for_event, persist_claims, quote_supported
from .llm import LLM, get_llm

# ---------- esquemas de salida (docs/spec/05 §4) ----------


class ExtractedEntity(BaseModel):
    name: str
    kind: str
    qid_candidate: str | None = None
    salience: float = 0.5


class ExtractedClaim(BaseModel):
    text_es: str
    text_original: str
    quote: str
    level: str = "fact"
    attributed_to: str | None = None
    check_worthy: float = 0.5
    time: str | None = None
    place: str | None = None


class ExtractorOutput(BaseModel):
    entities: list[ExtractedEntity] = Field(default_factory=list)
    claims: list[ExtractedClaim] = Field(default_factory=list)


class NeutralTitle(BaseModel):
    title_es: str
    domain: str


class Tradition(BaseModel):
    name: str
    key_works: list[str] = Field(default_factory=list)
    position_sketch: str


class NormativeQuestion(BaseModel):
    question: str
    traditions: list[Tradition]


class NormativeTranslation(BaseModel):
    event_id: str
    questions: list[NormativeQuestion]
    uncertainties: list[str] = Field(default_factory=list)


class TailRisk(BaseModel):
    description: str
    rough_probability: float


class RedTeamReport(BaseModel):
    strongest_alternative: str
    discriminating_evidence: list[str]
    likely_biases: list[str]
    tail_risks: list[TailRisk]
    question_nobody_asks: str


class ForecasterOutput(BaseModel):
    reference_class: str
    base_rate: float
    decomposition: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    probability: float
    what_would_change_my_mind: list[str] = Field(default_factory=list)


class AggregatorOutput(BaseModel):
    probability: float
    weights_rationale: str
    market_deviation_rationale: str | None = None
    summary_3_lines: str


class Scenario(BaseModel):
    name: str
    probability: float
    triggers: list[str]
    early_signals: list[str]
    description: str


class WhatIfOutput(BaseModel):
    scenarios: list[Scenario]
    red_team_objection: str
    uncertainties: list[str] = Field(default_factory=list)


class SessionSummary(BaseModel):
    concepts_used: list[str] = Field(default_factory=list)
    weak_points: list[str] = Field(default_factory=list)
    suggested_readings: list[str] = Field(default_factory=list)
    cards_to_create: list[str] = Field(default_factory=list)


# ---------- contexto mínimo ----------


def study_context() -> str:
    prof = profile_config()
    est = prof.get("estudios", {}) or {}
    courses = [c.get("nombre") for c in est.get("asignaturas_en_curso", []) or []]
    bib = []
    for c in est.get("asignaturas_en_curso", []) or []:
        bib += c.get("bibliografia", []) or []
    interests = est.get("intereses_teoricos_semilla", []) or []
    return (
        "Contexto del usuario (solo estudios; nada más se comparte): "
        f"grado en {est.get('grado', 'FPE+RRII')}; asignaturas: {', '.join(courses)}; "
        f"bibliografía: {'; '.join(bib[:12])}; intereses: {'; '.join(interests)}."
    )


def event_context(db: Database, event_id: str, max_claims: int = 20, max_docs: int = 15) -> str:
    ev = db.one("SELECT * FROM event WHERE id = ?", (event_id,))
    if not ev:
        raise KeyError("evento no encontrado")
    claims = claims_for_event(db, event_id, limit=max_claims)
    docs = db.all(
        """SELECT d.id, d.title, d.lede, d.published_at, d.lang, s.name, s.tier, s.ideology_label, s.region_bloc
           FROM document d JOIN source s ON s.id = d.source_id WHERE d.event_id = ? ORDER BY d.published_at LIMIT ?""",
        (event_id, max_docs),
    )
    cov = loads(ev["coverage_stats"], {}) or {}
    lines = [
        f"<evento id=\"{event_id}\">",
        f"Título provisional: {ev['title_neutral']}",
        f"Dominio: {ev['domain']} · Países: {', '.join(loads(ev['countries'], []))} · Materialidad: {ev['materiality']}",
        f"Cobertura: {cov.get('n_sources', 0)} fuentes, {cov.get('n_primary', 0)} primarias, idiomas {cov.get('langs', [])}; silencios: {[s['ecosystem'] for s in cov.get('silences', [])]}",
        "Afirmaciones registradas (claim_id · nivel · estado · texto · fuente):",
    ]
    for c in claims:
        lines.append(f"- {c['id']} · {c['level']} · {c['status']} · «{c['text_canonical']}» · {c['source_name']} (tier {c['source_tier']}) · doc {c['document_id']}")
    lines.append("Documentos (document_id · fuente · tier · ecosistema · titular · entradilla):")
    for d in docs:
        lines.append(f"<documento id=\"{d['id']}\" fuente=\"{d['name']}\" tier=\"{d['tier']}\" ideologia=\"{d['ideology_label']}\" bloque=\"{d['region_bloc']}\" fecha=\"{d['published_at']}\">{d['title']} — {(d['lede'] or '')[:400]}</documento>")
    lines.append("</evento>")
    return "\n".join(lines)


# ---------- agentes de línea ----------


def extract_claims_llm(db: Database, doc: dict[str, Any], source: dict[str, Any], llm: LLM | None = None) -> list[ClaimCandidate]:
    llm = llm or get_llm(db)
    text = "\n".join(p for p in (doc.get("title"), doc.get("lede"), doc.get("text")) if p)[:12000]
    user = (
        f"Documento a procesar:\n<documento id=\"{doc['id']}\" fuente=\"{source.get('name')}\" idioma=\"{doc.get('lang')}\" fecha=\"{doc.get('published_at')}\">\n{text}\n</documento>\n"
        "Extrae entidades y afirmaciones atómicas con cita literal según tu contrato. Máximo 8 afirmaciones."
    )
    res = llm.complete("bulk", "extractor", user, module="ingest", schema=ExtractorOutput, meta={"document_id": doc["id"]})
    out: list[ClaimCandidate] = []
    dropped = 0
    version = llm.load_prompt("extractor")[1]
    tag = f"{res.model}:extractor@{version}"
    for c in (res.parsed.claims if res.parsed else []):
        if not quote_supported(c.quote, text):
            dropped += 1
            continue
        level = c.level if c.level in ("fact", "data", "academic", "opinion") else "fact"
        out.append(ClaimCandidate(text=c.text_es, quote=c.quote[:300], level=level, check_worthy=max(0.0, min(1.0, c.check_worthy)), attributed_to=c.attributed_to, extracted_by=tag, meta={"text_original": c.text_original}))
    if dropped:
        with db.tx() as conn:
            conn.execute("UPDATE llm_call SET meta = json_set(meta, '$.dropped_unsupported_quotes', ?) WHERE id = (SELECT MAX(id) FROM llm_call)", (dropped,))
    return out


def neutral_title(db: Database, event_id: str, llm: LLM | None = None) -> str | None:
    llm = llm or get_llm(db)
    claims = claims_for_event(db, event_id, limit=10)
    if not claims:
        return None
    facts = "\n".join(f"- ({c['status']}) {c['text_canonical']}" for c in claims if c["level"] != "opinion")
    user = (
        "A partir SOLO de estas afirmaciones registradas, escribe un titular neutro en español (máx. 110 caracteres), sin adjetivos "
        "valorativos, en presente, con el actor y la acción; y clasifica el dominio (politics|economy|conflict|society|technology|health|environment|law).\n"
        f"{facts}"
    )
    res = llm.complete("bulk", "extractor", user, module="events", schema=NeutralTitle, max_tokens=300, meta={"event_id": event_id, "task": "neutral_title"})
    if res.parsed and res.parsed.title_es:
        with db.tx() as conn:
            conn.execute("UPDATE event SET title_neutral = ?, title_source = 'llm', domain = COALESCE(?, domain) WHERE id = ?", (res.parsed.title_es.strip(), res.parsed.domain, event_id))
        return res.parsed.title_es
    return None


# ---------- agentes bajo demanda (streaming) ----------


def _start_run(db: Database, kind: str, ref: str | None) -> str:
    rid = new_id()
    with db.tx() as conn:
        conn.execute("INSERT INTO agent_run(id, kind, ref, status, created_at) VALUES (?,?,?,?,?)", (rid, kind, ref, "running", now_iso()))
    return rid


def _finish_run(db: Database, rid: str, output: Any, ok: bool = True) -> None:
    with db.tx() as conn:
        conn.execute("UPDATE agent_run SET status = ?, output = ?, finished_at = ? WHERE id = ?", ("done" if ok else "error", dumps(output), now_iso(), rid))


def stream_agent(db: Database, kind: str, agent: str, tier: str, user: str, ref: str | None = None, extra_system: str | None = None, history: list[dict[str, Any]] | None = None, module: str = "on_demand") -> Iterator[dict[str, Any]]:
    """Genera eventos SSE: {type: start|delta|done|error}. Guarda el resultado en agent_run."""
    llm = get_llm(db)
    rid = _start_run(db, kind, ref)
    yield {"type": "start", "run_id": rid, "agent": agent, "model": llm.model_for(tier) if llm.enabled else None}
    chunks: list[str] = []
    try:
        for delta in llm.stream(tier, agent, user, module=module, extra_system=extra_system, history=history, meta={"run_id": rid, "ref": ref}):
            chunks.append(delta)
            yield {"type": "delta", "text": delta}
    except Exception as e:  # noqa: BLE001
        _finish_run(db, rid, {"error": str(e), "partial": "".join(chunks)}, ok=False)
        yield {"type": "error", "message": str(e)}
        return
    text = "".join(chunks)
    _finish_run(db, rid, {"text": text})
    yield {"type": "done", "run_id": rid, "text": text}


def deepen(db: Database, event_id: str) -> Iterator[dict[str, Any]]:
    ctx = event_context(db, event_id)
    user = (
        f"{ctx}\n\nRedacta el dossier del evento (EventDossier) en markdown con secciones: QUÉ HA PASADO (5-8 afirmaciones, cada una con su claim_id "
        "entre corchetes y su estado), LO QUE SABEMOS / LO QUE NO SABEMOS, DISPUTADO, CONTEXTO, IMPACTO (mercados y, si procede, canal de exposición), "
        "y 1-3 PREGUNTAS DE PRONÓSTICO resolubles (criterio, fuente, fecha). Nada sin cita."
    )
    return stream_agent(db, "deepen", "editor_jefe", "synthesis", user, ref=event_id, extra_system=study_context(), module="event_analysis")


def explain_60s(db: Database, event_id: str) -> Iterator[dict[str, Any]]:
    ctx = event_context(db, event_id, max_claims=10, max_docs=6)
    user = f"{ctx}\n\nExplícame este evento en 60 segundos de lectura (≤ 120 palabras), solo con afirmaciones registradas (cita claim_id), y termina con la pregunta abierta más importante."
    return stream_agent(db, "explain", "analista_regional", "analysis", user, ref=event_id)


def lens(db: Database, event_id: str | None, tradition: str, free_text: str | None = None) -> Iterator[dict[str, Any]]:
    ctx = event_context(db, event_id, max_claims=10, max_docs=6) if event_id else f"<texto>{free_text}</texto>"
    user = (
        f"{ctx}\n\n¿Cómo interpretaría esto la tradición o el autor «{tradition}»? Marca en la primera línea que es una RECONSTRUCCIÓN. "
        "Cita obras concretas (título y año) y distingue lo que el autor dijo de lo que se infiere. Termina con la mejor objeción desde otra tradición."
    )
    return stream_agent(db, "lens", "filosofo", "synthesis", user, ref=event_id, extra_system=study_context())


def socratic(db: Database, mode: str, message: str, history: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    user = f"[modo: {mode}] {message}"
    return stream_agent(db, "socratic", "tutor_socratico", "analysis", user, ref=mode, extra_system=study_context(), history=history)


def what_changed_country(db: Database, iso2: str, days: int) -> Iterator[dict[str, Any]]:
    rows = db.all(
        """SELECT id, title_neutral, materiality, domain, last_update_at FROM event
           WHERE countries LIKE ? AND last_update_at >= datetime('now', ?) AND status != 'merged'
           ORDER BY materiality DESC LIMIT 25""",
        (f'%"{iso2}"%', f"-{days} days"),
    )
    lines = [f"País: {iso2}. Ventana: {days} días. Eventos registrados (event_id · materialidad · dominio · título):"]
    for r in rows:
        lines.append(f"- {r['id']} · {r['materiality']} · {r['domain']} · {r['title_neutral']}")
        for c in claims_for_event(db, r["id"], limit=3):
            lines.append(f"    · claim {c['id']} ({c['status']}): {c['text_canonical']}")
    user = "\n".join(lines) + "\n\nDevuelve las N cosas que han cambiado MATERIALMENTE (no titulares), cada una con claim_id, y separa hechos de interpretación."
    return stream_agent(db, "what_changed", "analista_regional", "analysis", user, ref=iso2)


# ---------- agentes con salida estructurada ----------


def normative_translation(db: Database, event_id: str) -> dict[str, Any]:
    llm = get_llm(db)
    ctx = event_context(db, event_id, max_claims=10, max_docs=6)
    res = llm.complete("synthesis", "filosofo", f"{ctx}\n\nAplica el traductor normativo: 1-3 cuestiones normativas con 2-4 tradiciones cada una. Devuelve NormativeTranslation.", module="agora", schema=NormativeTranslation, extra_system=study_context(), meta={"event_id": event_id})
    out = res.parsed.model_dump() if res.parsed else {}
    out["cost_usd"] = res.cost_usd
    out["model"] = res.model
    rid = _start_run(db, "normative", event_id)
    _finish_run(db, rid, out)
    return out


def red_team(db: Database, event_id: str) -> dict[str, Any]:
    llm = get_llm(db)
    ctx = event_context(db, event_id)
    res = llm.complete("synthesis", "equipo_rojo", f"{ctx}\n\nAtaca la interpretación dominante. Devuelve RedTeamReport.", module="event_analysis", schema=RedTeamReport, meta={"event_id": event_id})
    out = res.parsed.model_dump() if res.parsed else {}
    out["cost_usd"] = res.cost_usd
    out["model"] = res.model
    rid = _start_run(db, "red_team", event_id)
    _finish_run(db, rid, out)
    return out


def what_if(db: Database, event_id: str | None, premise: str) -> dict[str, Any]:
    llm = get_llm(db)
    ctx = event_context(db, event_id, max_claims=10, max_docs=6) if event_id else ""
    user = f"{ctx}\n\nSIMULADOR modo C. Premisa: «{premise}». Propón 3-5 trayectorias con probabilidad (suman ≤ 1), desencadenantes y señales tempranas; añade la mejor objeción del equipo rojo. Etiqueta: SIMULACIÓN — no es predicción."
    res = llm.complete("analysis", "superpronosticador", user, module="simulator", schema=WhatIfOutput, meta={"event_id": event_id})
    out = res.parsed.model_dump() if res.parsed else {}
    out["label"] = "SIMULACIÓN — no es predicción"
    out["cost_usd"] = res.cost_usd
    rid = _start_run(db, "what_if", event_id)
    _finish_run(db, rid, out)
    return out


APPROACHES = ["outside_view", "inside_view", "devils_advocate", "market_aware", "historian"]


def forecast_ensemble(db: Database, question_id: str, n: int | None = None) -> dict[str, Any]:
    """Ensemble N + agregación (docs/spec/06 §3). Registra cada pieza por separado."""
    llm = get_llm(db)
    q = db.one("SELECT * FROM forecast_question WHERE id = ?", (question_id,))
    if not q:
        raise KeyError("pregunta no encontrada")
    from .config_loader import budget_config

    n = n or int(budget_config().get("limits", {}).get("forecast_ensemble_size", 5))
    market = db.one("SELECT probability, venue, question FROM prediction_market WHERE id = ?", ((loads(q["market_links"], []) or [{}])[0].get("id", ""),))
    context_evt = event_context(db, q["origin_event_id"], max_claims=12, max_docs=8) if q["origin_event_id"] else ""
    base = f"Pregunta: {q['title']}\nCriterio de resolución: {q['resolution_criteria']}\nFuente: {q['resolution_source']}\nCierre: {q['close_at']}\nTasa base registrada: {q['base_rate']} ({q['base_rate_note']})\n{context_evt}"
    individual = []
    for i in range(n):
        approach = APPROACHES[i % len(APPROACHES)]
        user = f"{base}\n\nRol A (pronosticador individual). Enfoque asignado: {approach}. No conoces otros pronósticos. Devuelve ForecasterOutput."
        try:
            res = llm.complete("analysis", "superpronosticador", user, module="forecasting", schema=ForecasterOutput, meta={"question_id": question_id, "approach": approach})
        except Exception as e:  # noqa: BLE001
            individual.append({"approach": approach, "error": str(e)})
            continue
        p = fmath.clip(res.parsed.probability) if res.parsed else None
        individual.append({"approach": approach, "probability": p, "output": res.parsed.model_dump() if res.parsed else None, "cost_usd": res.cost_usd})
        if p is not None:
            _store_forecast(db, question_id, f"agent:{approach}", p, (res.parsed.reference_class if res.parsed else ""))
    probs = [x["probability"] for x in individual if x.get("probability") is not None]
    if not probs:
        return {"error": "ningún pronosticador devolvió probabilidad", "individual": individual}
    agg = fmath.aggregate_ensemble(probs)
    _store_forecast(db, question_id, "atlas_ensemble_raw", agg["raw"], "media de log-odds")
    _store_forecast(db, question_id, "atlas_ensemble_extremized", agg["extremized"], f"extremización a={agg['a']}")
    m = float(market["probability"]) if market else None
    p_final = fmath.blend_with_market(agg["extremized"], m, alpha=0.4)
    # agregador LLM (rol B)
    summary = "\n".join(f"- {x['approach']}: p={x.get('probability')} · {json.dumps(x.get('output'), ensure_ascii=False)[:600]}" for x in individual)
    user_b = f"{base}\n\nRol B (agregador). Pronósticos individuales:\n{summary}\nMercado: {m if m is not None else 'sin mercado enlazado'}\nAgregación matemática: raw={agg['raw']:.3f}, extremizada={agg['extremized']:.3f}, mezcla con mercado={p_final:.3f}. Devuelve AggregatorOutput."
    adjusted = None
    try:
        res_b = llm.complete("synthesis", "superpronosticador", user_b, module="forecasting", schema=AggregatorOutput, meta={"question_id": question_id, "role": "aggregator"})
        if res_b.parsed:
            adjusted = res_b.parsed.model_dump()
            _store_forecast(db, question_id, "atlas_llm_adjusted", fmath.clip(res_b.parsed.probability), res_b.parsed.summary_3_lines)
    except Exception as e:  # noqa: BLE001
        adjusted = {"error": str(e)}
    _store_forecast(db, question_id, "atlas_final", p_final, "sigmoid(0.4·logit(ens)+0.6·logit(mercado))" if m is not None else "ensemble extremizado (sin mercado)")
    out = {"question_id": question_id, "individual": individual, "aggregate": agg, "market": m, "final": p_final, "aggregator": adjusted}
    rid = _start_run(db, "forecast_ensemble", question_id)
    _finish_run(db, rid, out)
    return out


def _store_forecast(db: Database, question_id: str, forecaster: str, p: float, rationale: str) -> None:
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO forecast(id, question_id, forecaster, probability, rationale, made_at) VALUES (?,?,?,?,?,?)",
            (new_id(), question_id, forecaster, round(float(p), 4), rationale, now_iso()),
        )


def redact_brief(db: Database, brief_id: str) -> dict[str, Any]:
    """El editor jefe redacta el brief compuesto por reglas. Crítico (se permite hasta el 100% del presupuesto)."""
    llm = get_llm(db)
    row = db.one("SELECT * FROM brief WHERE id = ?", (brief_id,))
    if not row:
        raise KeyError("brief no encontrado")
    content = loads(row["content"], {})
    user = (
        "Contenido del brief compuesto por reglas (eventos, afirmaciones con claim_id, divergencias, primarias, conceptos):\n"
        f"{json.dumps(content, ensure_ascii=False)[:24000]}\n\n"
        "Redacta el Brief de estudio en markdown: por sección, cada ítem en ≤ 4 líneas (hechos con [claim_id], divergencia en una línea, primaria, por qué importa, concepto del grado). "
        "Cierra con la pregunta de pronóstico y la cuestión socrática. No añadas hechos que no estén en el contenido."
    )
    res = llm.complete("synthesis", "editor_jefe", user, module="brief", critical=True, extra_system=study_context(), max_tokens=6000, meta={"brief_id": brief_id})
    content["redaction_md"] = res.text
    content["composed_by"] = "llm"
    with db.tx() as conn:
        conn.execute("UPDATE brief SET composed_by = 'llm', content = ? WHERE id = ?", (dumps(content), brief_id))
    return {"brief_id": brief_id, "cost_usd": res.cost_usd, "model": res.model, "redaction_md": res.text}


def persist_llm_claims_for_document(db: Database, doc: dict[str, Any], source: dict[str, Any], event_id: str | None) -> dict[str, int]:
    cands = extract_claims_llm(db, doc, source)
    return persist_claims(db, doc, source, event_id, cands)
