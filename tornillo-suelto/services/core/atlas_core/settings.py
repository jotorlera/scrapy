"""Rutas y variables de entorno. Un solo lugar para saber dónde está cada cosa."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# services/core/atlas_core/settings.py -> raíz del proyecto (tornillo-suelto/)
ROOT = Path(__file__).resolve().parents[3]


def _find_env_file() -> str | None:
    p = ROOT / ".env"
    return str(p) if p.exists() else None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_find_env_file(), extra="ignore")

    anthropic_api_key: str | None = None
    fred_api_key: str | None = None
    atlas_user_agent: str = "TORNILLO-SUELTO/0.1 (ATLAS personal research crawler; contact: local user)"
    atlas_demo: int = 0
    atlas_embeddings: str = "hashing"  # hashing | bge-m3
    atlas_db_path: str | None = None
    atlas_host: str = "127.0.0.1"
    atlas_port: int = 8765
    atlas_scheduler: int = 1
    atlas_ingest_concurrency: int = 12
    atlas_timezone: str = "Europe/Monaco"

    @property
    def db_path(self) -> Path:
        if self.atlas_db_path:
            return Path(self.atlas_db_path)
        return ROOT / "data" / "atlas.db"

    @property
    def config_dir(self) -> Path:
        return ROOT / "config"

    @property
    def prompts_dir(self) -> Path:
        return ROOT / "prompts" / "runtime"

    @property
    def web_dist(self) -> Path:
        return ROOT / "apps" / "web" / "dist"

    @property
    def data_dir(self) -> Path:
        return ROOT / "data"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


settings = Settings()
os.makedirs(settings.data_dir, exist_ok=True)
