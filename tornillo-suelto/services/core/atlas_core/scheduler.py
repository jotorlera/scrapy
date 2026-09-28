"""Planificador en proceso (ADR-0001): ingesta, mercados, recálculo y Brief diario, sin Redis."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from .config_loader import profile_config
from .db import Database, dumps, new_id, now_iso, since_iso
from .engines.brief import compose_brief
from .pipeline import recompute_events, run_ingest, run_markets
from .settings import settings

log = logging.getLogger("atlas.scheduler")

INGEST_EVERY = 15 * 60
MARKETS_EVERY = 15 * 60
RECOMPUTE_EVERY = 60 * 60


class Scheduler:
    def __init__(self, db: Database):
        self.db = db
        self.running = False
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        self.running = True
        await asyncio.sleep(3)
        last_ingest = last_markets = last_recompute = 0.0
        loop = asyncio.get_running_loop()
        while not self._stop.is_set():
            now = loop.time()
            try:
                if now - last_markets >= MARKETS_EVERY:
                    last_markets = now
                    await run_markets(self.db)
                if now - last_ingest >= INGEST_EVERY:
                    last_ingest = now
                    await run_ingest(self.db)
                    await self._maybe_brief()
                if now - last_recompute >= RECOMPUTE_EVERY:
                    last_recompute = now
                    await asyncio.to_thread(recompute_events, self.db)
                    await self._alerts()
            except Exception as e:  # noqa: BLE001 - el planificador nunca muere
                log.exception("scheduler: %s", e)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=30)
            except TimeoutError:
                pass
        self.running = False

    async def _maybe_brief(self) -> None:
        """Genera el Brief del día si ya pasó la hora configurada y no existe."""
        prof = profile_config().get("usuario", {}) or {}
        tz = ZoneInfo(prof.get("zona_horaria") or settings.atlas_timezone)
        hh, mm = (prof.get("hora_brief") or "07:00").split(":")
        local = datetime.now(tz)
        if (local.hour, local.minute) < (int(hh), int(mm)):
            return
        today = local.date().isoformat()
        if self.db.one("SELECT 1 FROM brief WHERE date = ? AND kind = 'study'", (today,)):
            return
        if (
            self.db.scalar("SELECT COUNT(*) FROM event WHERE last_update_at >= ?", (since_iso(days=1),), 0)
            < 5
        ):
            return
        await asyncio.to_thread(compose_brief, self.db, "study", 24)
        await asyncio.to_thread(compose_brief, self.db, "executive", 24)
        if settings.llm_enabled:
            try:
                from .agents import redact_brief

                b = self.db.one(
                    "SELECT id FROM brief WHERE date = ? AND kind = 'study' ORDER BY created_at DESC LIMIT 1",
                    (today,),
                )
                if b:
                    await asyncio.to_thread(redact_brief, self.db, b["id"])
            except Exception as e:  # noqa: BLE001
                log.warning("brief LLM: %s", e)
        with self.db.tx() as conn:
            conn.execute(
                "INSERT INTO alert(id, kind, title, body, ref, created_at) VALUES (?,?,?,?,?,?)",
                (
                    new_id(),
                    "brief",
                    f"Brief del {today} disponible",
                    "Lectura estimada: 10 minutos.",
                    dumps({"route": "/brief"}),
                    now_iso(),
                ),
            )

    async def _alerts(self) -> None:
        """Alertas por materialidad alta (umbral push_alert de materiality.yaml)."""
        from .config_loader import materiality_config

        th = float((materiality_config().get("thresholds") or {}).get("push_alert", 80))
        rows = self.db.all(
            "SELECT id, title_neutral, materiality FROM event WHERE materiality >= ? AND last_update_at >= ?",
            (th, since_iso(days=1)),
        )
        with self.db.tx() as conn:
            for r in rows:
                if conn.execute(
                    "SELECT 1 FROM alert WHERE kind = 'materiality' AND json_extract(ref, '$.event_id') = ?",
                    (r["id"],),
                ).fetchone():
                    continue
                conn.execute(
                    "INSERT INTO alert(id, kind, title, body, ref, created_at) VALUES (?,?,?,?,?,?)",
                    (
                        new_id(),
                        "materiality",
                        f"Materialidad {r['materiality']:.0f}: {r['title_neutral'][:100]}",
                        None,
                        dumps({"event_id": r["id"], "route": f"/eventos/{r['id']}"}),
                        now_iso(),
                    ),
                )
