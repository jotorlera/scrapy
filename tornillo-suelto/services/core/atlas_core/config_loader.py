"""Carga de los YAML de config/ con caché. Nada de nombres de modelo ni pesos escritos a mano en el código."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import yaml

from .settings import settings


def _load(name: str) -> Any:
    p: Path = settings.config_dir / name
    if not p.exists():
        return {}
    with p.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@cache
def models_config() -> dict[str, Any]:
    return _load("models.yaml")


@cache
def budget_config() -> dict[str, Any]:
    return _load("budget.yaml")


@cache
def materiality_config() -> dict[str, Any]:
    return _load("materiality.yaml")


@cache
def countries_config() -> dict[str, Any]:
    return _load("paises.yaml")


@cache
def profile_config() -> dict[str, Any]:
    """Perfil personal (config/perfil.yaml, fuera de git); si no existe, la plantilla perfil.example.yaml."""
    if (settings.config_dir / "perfil.yaml").exists():
        return _load("perfil.yaml")
    return _load("perfil.example.yaml")


@cache
def causal_channels_config() -> dict[str, Any]:
    return _load("causal_channels.yaml")


@cache
def sources_seed() -> list[dict[str, Any]]:
    """Aplana fuentes.seed.yaml: cada fuente lleva `group` con el nombre de su sección."""
    raw = _load("fuentes.seed.yaml")
    defaults = raw.get("defaults", {}) if isinstance(raw, dict) else {}
    out: list[dict[str, Any]] = []
    for group, items in raw.items():
        if group == "defaults" or not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict) or "slug" not in it:
                continue
            row = {**defaults, **it, "group": group}
            out.append(row)
    return out


@cache
def feeds_catalog() -> dict[str, list[str]]:
    """Feeds curados por slug (config/feeds.yaml). Complementa el autodescubrimiento."""
    raw = _load("feeds.yaml")
    out: dict[str, list[str]] = {}
    for slug, feeds in (raw or {}).items():
        if isinstance(feeds, str):
            out[slug] = [feeds]
        elif isinstance(feeds, list):
            out[slug] = [f for f in feeds if isinstance(f, str)]
    return out


def attention_level(iso2: str) -> str:
    cfg = countries_config()
    extra = set(profile_config().get("preferencias_atlas", {}).get("paises_nivel_A_extra", []) or [])
    if iso2 in set(cfg.get("A", [])) | extra:
        return "A"
    if iso2 in set(cfg.get("B", [])):
        return "B"
    return "C"


def clear_caches() -> None:
    for fn in (
        models_config,
        budget_config,
        materiality_config,
        countries_config,
        profile_config,
        causal_channels_config,
        sources_seed,
        feeds_catalog,
    ):
        fn.cache_clear()
