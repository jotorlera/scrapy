"""Guardarraíl de privacidad: config/perfil.yaml (nombre, estudios, negocios) nunca vuelve al repositorio.

Se ejecuta con `make test`. Falla si git rastrea el archivo o si .gitignore dejó de cubrirlo; comprueba además que
la plantilla versionada no contiene datos reales del perfil local y que la suite no depende del perfil personal.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "config/perfil.yaml"
EXAMPLE = ROOT / "config" / "perfil.example.yaml"


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)


def _require_git_checkout() -> None:
    if shutil.which("git") is None:
        pytest.skip("git no disponible")
    if _git("rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
        pytest.skip("no es un checkout de git (tarball o copia sin .git)")


def test_profile_is_not_tracked_by_git():
    _require_git_checkout()
    r = _git("ls-files", "--error-unmatch", PROFILE)
    assert r.returncode != 0, f"{PROFILE} está versionado: `git rm --cached {PROFILE}` y añádelo a .gitignore"


def test_profile_is_gitignored():
    _require_git_checkout()
    r = _git("check-ignore", "-q", PROFILE)
    assert r.returncode == 0, f"{PROFILE} no está en .gitignore"


def test_example_profile_is_versioned_and_generic():
    _require_git_checkout()
    assert EXAMPLE.exists(), "falta config/perfil.example.yaml (plantilla del perfil)"
    assert _git("ls-files", "--error-unmatch", "config/perfil.example.yaml").returncode == 0 or _git(
        "status", "--porcelain", "config/perfil.example.yaml"
    ).stdout.startswith(("??", "A ")), "config/perfil.example.yaml debe estar versionado"
    data = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8")) or {}
    assert {"usuario", "estudios", "negocios", "negocios_contexto", "preferencias_atlas"} <= set(data)
    assert isinstance(data["negocios"], list) and data["negocios"]
    real = ROOT / "config" / "perfil.yaml"
    if not real.exists():
        return
    # Ningún valor identificativo del perfil local (nombre, universidad, negocios, colaboraciones) en la plantilla.
    local = yaml.safe_load(real.read_text(encoding="utf-8")) or {}
    example_text = EXAMPLE.read_text(encoding="utf-8")
    sensitive = [
        (local.get("usuario") or {}).get("nombre"),
        (local.get("usuario") or {}).get("firma_trabajos"),
        (local.get("estudios") or {}).get("universidad"),
        *[b.get("nombre") for b in local.get("negocios") or []],
        *((local.get("negocios_contexto") or {}).get("colaboraciones") or []),
    ]
    for value in filter(None, sensitive):
        assert value not in example_text, f"la plantilla contiene un dato del perfil local: {value!r}"


def test_suite_uses_the_fixture_profile_not_the_personal_one():
    from atlas_core.config_loader import profile_config

    prof = profile_config()
    assert prof["usuario"]["nombre"] == "Usuaria de Pruebas"
    assert len(prof["negocios"]) == 4
