"""Capa LLM: un único punto de entrada a la API de Anthropic (ADR-0004).

- Modelos por nivel desde config/models.yaml (nunca en el código).
- Presupuesto diario desde config/budget.yaml: al 80% se pausan las tareas no críticas; al 100% se para todo.
- Cada llamada se registra en `llm_call` con tokens (incluida caché), coste, latencia y resultado. La respuesta
  se obtiene SIEMPRE antes de validarla, para que el registro lleve el uso real aunque la salida no valide.
- Salida estructurada con `output_config.format` (json_schema) y validación Pydantic propia; un reintento con el
  error si no valida. `stop_reason` se comprueba antes de validar: `refusal` no se reintenta (`LLMRefused`),
  `max_tokens` se reintenta una vez con más margen (`LLMTruncated` si vuelve a cortarse).
- Un stream abandonado por el consumidor (GeneratorExit) se registra igualmente, con la salida estimada y marcada.
- Sin clave: `LLMUnavailable`, que la API traduce a un estado explícito para la UI.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from .config_loader import budget_config, models_config
from .db import Database, dumps, now_iso
from .settings import settings

T = TypeVar("T", bound=BaseModel)

# Tope absoluto de `max_tokens` al reintentar una salida truncada (config/models.yaml: max_tokens_retry_cap).
DEFAULT_MAX_TOKENS_RETRY_CAP = 16000
# Estimación de salida para un stream abandonado (el snapshot solo trae los tokens de `message_start`).
_CHARS_PER_TOKEN = 4


class LLMUnavailable(RuntimeError):
    """No hay ANTHROPIC_API_KEY: los agentes están desactivados."""


class BudgetExceeded(RuntimeError):
    """Tope diario alcanzado."""


class LLMRefused(RuntimeError):
    """El modelo rehusó (`stop_reason="refusal"`, HTTP 200). No se reintenta: el mismo prompt volvería a serlo."""

    def __init__(self, message: str, category: str | None = None, explanation: str | None = None):
        super().__init__(message)
        self.category = category
        self.explanation = explanation


class LLMTruncated(RuntimeError):
    """La salida se cortó por `max_tokens` también tras reintentar con más margen."""


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read: int = 0
    cache_write: int = 0

    def cost(self, model: str) -> float:
        p = (models_config().get("pricing_usd_per_mtok") or {}).get(model) or {}
        return (
            self.input_tokens * float(p.get("input", 0))
            + self.output_tokens * float(p.get("output", 0))
            + self.cache_read * float(p.get("cache_read", 0))
            + self.cache_write * float(p.get("cache_write", 0))
        ) / 1_000_000.0


@dataclass
class LLMResult:
    text: str
    parsed: Any = None
    model: str = ""
    usage: Usage = field(default_factory=Usage)
    cost_usd: float = 0.0
    latency_ms: int = 0
    stop_reason: str | None = None
    call_id: int | None = None  # fila de `llm_call` de la respuesta aceptada (para anotar meta a posteriori)


_PROMPT_VERSION_RE = re.compile(r"\bv(\d+)\b")


def _output_format(schema: type[BaseModel]) -> dict[str, Any]:
    """`output_config.format` canónico. `transform_schema` (SDK) adapta el esquema Pydantic a lo que acepta la API."""
    try:
        from anthropic import transform_schema

        json_schema = transform_schema(schema)
    except ImportError:  # pragma: no cover - SDK sin ayudante: esquema Pydantic tal cual
        json_schema = schema.model_json_schema()
    return {"type": "json_schema", "schema": json_schema}


class LLM:
    def __init__(self, db: Database):
        self.db = db
        self.cfg = models_config()
        self._client = None
        self._last_call_id: int | None = None
        if settings.llm_enabled:
            import anthropic

            self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key, max_retries=2)

    # ---------- configuración ----------
    @property
    def enabled(self) -> bool:
        return self._client is not None

    def tier(self, name: str) -> dict[str, Any]:
        tiers = self.cfg.get("tiers") or {}
        if name not in tiers:
            raise KeyError(f"tier desconocido: {name}")
        return tiers[name]

    def model_for(self, tier: str) -> str:
        return str(self.tier(tier)["model"])

    # ---------- prompts ----------
    def load_prompt(self, name: str) -> tuple[str, str]:
        p = settings.prompts_dir / f"{name}.md"
        if not p.exists():
            raise FileNotFoundError(f"prompt no encontrado: {name}")
        text = p.read_text(encoding="utf-8")
        first = text.splitlines()[0] if text else ""
        m = _PROMPT_VERSION_RE.search(first)
        version = m.group(1) if m else "1"
        return text, version

    def system_for(self, agent: str) -> tuple[list[dict[str, Any]], str]:
        common, _ = self.load_prompt("_comun")
        body, version = self.load_prompt(agent)
        # el preámbulo común y el contrato del agente son estables: se cachean
        system = [
            {"type": "text", "text": common, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": body, "cache_control": {"type": "ephemeral"}},
        ]
        return system, version

    # ---------- presupuesto ----------
    def spent_today(self) -> float:
        day = datetime.now(UTC).date().isoformat()
        v = self.db.scalar(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM llm_call WHERE substr(at, 1, 10) = ?", (day,), 0.0
        )
        return float(v or 0.0)

    def budget_state(self) -> dict[str, Any]:
        b = budget_config()
        cap = float(b.get("daily_cap_usd", 10.0))
        spent = self.spent_today()
        frac = spent / cap if cap > 0 else 1.0
        return {
            "daily_cap_usd": cap,
            "spent_today_usd": round(spent, 4),
            "fraction": round(frac, 3),
            "pause_noncritical": frac >= float(b.get("pause_noncritical_at", 0.8)),
            "hard_stop": frac >= 1.0,
            "enabled": self.enabled,
            "allocation": b.get("allocation", {}),
            "limits": b.get("limits", {}),
        }

    def _check(self, critical: bool) -> None:
        if not self.enabled:
            raise LLMUnavailable("Agentes desactivados: añade ANTHROPIC_API_KEY en .env")
        st = self.budget_state()
        if st["hard_stop"]:
            raise BudgetExceeded(
                f"Tope diario alcanzado ({st['spent_today_usd']:.2f} de {st['daily_cap_usd']:.2f} USD)"
            )
        if st["pause_noncritical"] and not critical:
            raise BudgetExceeded(
                f"80% del presupuesto diario gastado ({st['spent_today_usd']:.2f} USD): tareas no críticas en pausa"
            )

    # ---------- registro ----------
    def _log(
        self,
        module: str,
        agent: str,
        prompt_name: str,
        version: str,
        model: str,
        usage: Usage,
        latency_ms: int,
        ok: bool,
        error: str | None = None,
        meta: dict | None = None,
    ) -> float:
        cost = usage.cost(model)
        with self.db.tx() as conn:
            cur = conn.execute(
                """INSERT INTO llm_call(at, module, agent, prompt_name, prompt_version, model, input_tokens, output_tokens,
                   cache_read_tokens, cache_write_tokens, cost_usd, latency_ms, ok, error, meta)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    now_iso(),
                    module,
                    agent,
                    prompt_name,
                    version,
                    model,
                    usage.input_tokens,
                    usage.output_tokens,
                    usage.cache_read,
                    usage.cache_write,
                    round(cost, 6),
                    latency_ms,
                    1 if ok else 0,
                    error,
                    dumps(meta or {}),
                ),
            )
            self._last_call_id = cur.lastrowid
        return cost

    @staticmethod
    def _usage_of(resp: Any) -> Usage:
        u = getattr(resp, "usage", None)
        if u is None:
            return Usage()
        return Usage(
            input_tokens=int(getattr(u, "input_tokens", 0) or 0),
            output_tokens=int(getattr(u, "output_tokens", 0) or 0),
            cache_read=int(getattr(u, "cache_read_input_tokens", 0) or 0),
            cache_write=int(getattr(u, "cache_creation_input_tokens", 0) or 0),
        )

    @staticmethod
    def _stop_of(resp: Any) -> tuple[str | None, str | None, str | None]:
        """(stop_reason, categoría de la negativa, explicación). `stop_details` solo viene con `refusal`."""
        det = getattr(resp, "stop_details", None)
        return (
            getattr(resp, "stop_reason", None),
            getattr(det, "category", None),
            getattr(det, "explanation", None),
        )

    @staticmethod
    def _text_of(resp: Any) -> str:
        return "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")

    def _params(self, tier_name: str, max_tokens: int | None) -> dict[str, Any]:
        t = self.tier(tier_name)
        params: dict[str, Any] = {
            "model": t["model"],
            "max_tokens": int(max_tokens or t.get("max_tokens", 4096)),
        }
        thinking = t.get("thinking", "none")
        if thinking == "adaptive":
            params["thinking"] = {"type": "adaptive"}
            if t.get("effort"):
                params["output_config"] = {"effort": t["effort"]}
        return params

    def _retry_cap(self) -> int:
        return int(self.cfg.get("max_tokens_retry_cap", DEFAULT_MAX_TOKENS_RETRY_CAP))

    # ---------- llamadas ----------
    def complete(
        self,
        tier: str,
        agent: str,
        user: str,
        *,
        module: str,
        schema: type[T] | None = None,
        max_tokens: int | None = None,
        critical: bool = False,
        extra_system: str | None = None,
        meta: dict | None = None,
    ) -> LLMResult:
        """Una llamada. Con `schema`, pide `json_schema` a la API, valida la salida (Pydantic) y reintenta una vez
        con el error. Antes de validar comprueba `stop_reason`: `refusal` → `LLMRefused` (sin reintento);
        `max_tokens` → un reintento con el doble de margen y el MISMO prompt, luego `LLMTruncated`."""
        self._check(critical)
        system, version = self.system_for(agent)
        if extra_system:
            system = [*system, {"type": "text", "text": extra_system}]
        params = self._params(tier, max_tokens)
        if schema is not None:
            params["output_config"] = {**params.get("output_config", {}), "format": _output_format(schema)}
        model = params["model"]
        messages: list[dict[str, Any]] = [{"role": "user", "content": user}]
        retries = int(self.cfg.get("max_retries_on_schema_error", 1))
        cap = self._retry_cap()
        last_err: str | None = None
        for attempt in range(retries + 1):
            t0 = time.monotonic()
            try:
                resp = self._client.messages.create(system=system, messages=messages, **params)  # type: ignore[union-attr]
            except Exception as e:  # noqa: BLE001 - se registra y se relanza
                latency = int((time.monotonic() - t0) * 1000)
                self._log(
                    module,
                    agent,
                    agent,
                    version,
                    model,
                    Usage(),
                    latency,
                    False,
                    f"{type(e).__name__}: {e}",
                    meta,
                )
                raise
            latency = int((time.monotonic() - t0) * 1000)
            usage = self._usage_of(resp)  # uso real: la API facturó aunque la salida no sirva
            stop, category, explanation = self._stop_of(resp)
            info: dict[str, Any] = {**(meta or {}), "stop_reason": stop, "max_tokens": params["max_tokens"]}
            if category:
                info["refusal_category"] = category
            text = self._text_of(resp)
            if stop == "refusal":
                label = category or "sin categoría"
                self._log(
                    module, agent, agent, version, model, usage, latency, False, f"refusal: {label}", info
                )
                msg = f"El modelo rehusó la petición ({label})"
                raise LLMRefused(msg + (f": {explanation}" if explanation else ""), category, explanation)
            if stop == "max_tokens":
                self._log(module, agent, agent, version, model, usage, latency, False, "max_tokens", info)
                if attempt < retries and params["max_tokens"] < cap:
                    # mismo `messages`: un JSON cortado no se arregla con un turno assistant fabricado
                    params["max_tokens"] = min(2 * params["max_tokens"], cap)
                    continue
                raise LLMTruncated(
                    f"Salida cortada por max_tokens ({params['max_tokens']}) también tras reintentar con más margen"
                )
            parsed: Any = None
            if schema is not None:
                try:
                    parsed = schema.model_validate_json(text)
                except ValidationError as ve:
                    last_err = str(ve)[:800]
                    self._log(
                        module,
                        agent,
                        agent,
                        version,
                        model,
                        usage,
                        latency,
                        False,
                        "schema: " + last_err,
                        info,
                    )
                    if attempt < retries:
                        messages = [
                            *messages,
                            {"role": "assistant", "content": text or "(vacío)"},
                            {
                                "role": "user",
                                "content": f"La salida no valida contra el esquema: {last_err}. Devuelve solo el JSON correcto.",
                            },
                        ]
                        continue
                    raise ValueError(f"Salida no válida tras reintento: {last_err}") from ve
            elif not text.strip():
                # defensa contra contenido solo-thinking o vacío con end_turn: nunca se devuelve como éxito
                self._log(module, agent, agent, version, model, usage, latency, False, "empty", info)
                raise ValueError(f"Respuesta vacía del modelo (stop_reason={stop})")
            cost = self._log(module, agent, agent, version, model, usage, latency, True, None, info)
            return LLMResult(
                text=text,
                parsed=parsed,
                model=model,
                usage=usage,
                cost_usd=cost,
                latency_ms=latency,
                stop_reason=stop,
                call_id=self._last_call_id,
            )
        raise ValueError(last_err or "sin respuesta")

    def stream(
        self,
        tier: str,
        agent: str,
        user: str,
        *,
        module: str,
        max_tokens: int | None = None,
        critical: bool = False,
        extra_system: str | None = None,
        history: list[dict[str, Any]] | None = None,
        meta: dict | None = None,
        on_final: Callable[[Any], None] | None = None,
    ) -> Iterator[str]:
        """Generador de fragmentos de texto. Registra la llamada al terminar (también si el consumidor la
        abandona). `on_final` recibe el mensaje final (para leer `stop_reason`). Una negativa a mitad de stream
        se registra y lanza `LLMRefused`: la salida parcial de una negativa se descarta."""
        self._check(critical)
        system, version = self.system_for(agent)
        if extra_system:
            system = [*system, {"type": "text", "text": extra_system}]
        params = self._params(tier, max_tokens)
        model = params["model"]
        messages = [*(history or []), {"role": "user", "content": user}]
        t0 = time.monotonic()
        stream_obj: Any = None
        n_chars = 0
        try:
            with self._client.messages.stream(system=system, messages=messages, **params) as stream_obj:  # type: ignore[union-attr]
                for chunk in stream_obj.text_stream:
                    n_chars += len(chunk)
                    yield chunk
                final = stream_obj.get_final_message()
        except GeneratorExit:
            # consumidor desconectado: lo generado hasta aquí se factura igual → se registra con estimación marcada
            usage = Usage()
            try:
                if stream_obj is not None:
                    usage = self._usage_of(
                        stream_obj.current_message_snapshot
                    )  # AssertionError sin message_start
            except Exception:  # noqa: BLE001
                pass
            usage.output_tokens = max(
                usage.output_tokens, (n_chars + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN
            )
            self._log(
                module,
                agent,
                agent,
                version,
                model,
                usage,
                int((time.monotonic() - t0) * 1000),
                False,
                "aborted: consumidor desconectado",
                {**(meta or {}), "aborted": True, "output_tokens_estimated": True, "chars_streamed": n_chars},
            )
            raise
        except Exception as e:  # noqa: BLE001
            self._log(
                module,
                agent,
                agent,
                version,
                model,
                Usage(),
                int((time.monotonic() - t0) * 1000),
                False,
                f"{type(e).__name__}: {e}",
                meta,
            )
            raise
        latency = int((time.monotonic() - t0) * 1000)
        usage = self._usage_of(final)
        stop, category, explanation = self._stop_of(final)
        info: dict[str, Any] = {**(meta or {}), "stop_reason": stop}
        if category:
            info["refusal_category"] = category
        if stop == "refusal":
            label = category or "sin categoría"
            self._log(module, agent, agent, version, model, usage, latency, False, f"refusal: {label}", info)
            msg = f"El modelo rehusó la petición ({label})"
            raise LLMRefused(msg + (f": {explanation}" if explanation else ""), category, explanation)
        self._log(module, agent, agent, version, model, usage, latency, True, None, info)
        if on_final is not None:
            on_final(final)


_llm: LLM | None = None


def get_llm(db: Database) -> LLM:
    global _llm
    if _llm is None or _llm.db is not db:
        _llm = LLM(db)
    return _llm
