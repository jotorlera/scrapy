"""La mesa de agentes documentada coincide con los prompts realmente cableados en agents.py.

prompts/runtime/ contiene 16 contratos (más _comun.md), pero solo una parte se pasa a llm.complete/stream. README,
PROGRESS («Deuda técnica») y docs/PLANTEAMIENTO.md deben describir la mesa real; este test evita que vuelvan a
desalinearse: si se cablea un prompt nuevo, hay que actualizar WIRED y los textos.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS_PY = ROOT / "services" / "core" / "atlas_core" / "agents.py"
PROMPTS = ROOT / "prompts" / "runtime"

WIRED = {
    "extractor",
    "editor_jefe",
    "analista_regional",
    "filosofo",
    "tutor_socratico",
    "equipo_rojo",
    "superpronosticador",
}
UNWIRED = {
    "analista_conflicto",
    "analista_discurso",
    "auditor_evidencia",
    "clasificador_marcos",
    "estratega_corporativo",
    "estratega_mercados",
    "historiador",
    "macroeconomista",
}


def _prompt_names() -> set[str]:
    return {p.stem for p in PROMPTS.glob("*.md") if not p.stem.startswith("_")}


def _wired_in_agents() -> set[str]:
    src = AGENTS_PY.read_text(encoding="utf-8")
    literals = set(re.findall(r"""["']([a-z_]+)["']""", src))
    return literals & _prompt_names()


def test_prompt_catalog_is_the_documented_sixteen():
    assert _prompt_names() == WIRED | UNWIRED


def test_wired_prompts_match_the_documented_table():
    assert _wired_in_agents() == WIRED


def test_progress_lists_every_unwired_prompt_as_debt():
    progress = (ROOT / "PROGRESS.md").read_text(encoding="utf-8")
    for name in sorted(UNWIRED):
        assert name in progress, f"PROGRESS.md no declara el prompt sin cablear {name}"
    # El clasificador de marcos no debe presentarse como algo que «se activa con clave».
    assert "clasificador de marcos no se ejecuta sin clave" not in progress
