"""
Background task: stop VMs that have been idle for longer than IDLE_TIMEOUT.

Rules:
  - task_count == 0  (no in-flight requests)
  - (now - last_active) > settings.vm_idle_timeout seconds
  - VM process is still running
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from settings import settings

log = logging.getLogger(__name__)


class IdleReaper:
    def __init__(self, manager):
        self._manager = manager
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop(), name="idle-reaper")
        log.info("idle reaper started (timeout=%ds, interval=%ds)",
                 settings.vm_idle_timeout, settings.vm_reaper_interval)

    def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(settings.vm_reaper_interval)
                await self._reap_once()
            except asyncio.CancelledError:
                log.info("idle reaper stopping")
                return
            except Exception as e:
                log.exception("idle reaper error: %s", e)

    async def _reap_once(self) -> None:
        now = datetime.now(timezone.utc)
        to_stop: list[uuid.UUID] = []

        for user_id, vm in self._manager.active_vms.items():
            if vm.task_count > 0:
                continue
            idle_seconds = (now - vm.last_active).total_seconds()
            if idle_seconds >= settings.vm_idle_timeout:
                log.info(
                    "VM %s idle for %.0fs — scheduling shutdown",
                    vm.vm_id,
                    idle_seconds,
                )
                to_stop.append(user_id)

        for user_id in to_stop:
            try:
                await self._manager.stop(user_id, persist=True)
            except Exception as e:
                log.warning("failed to stop VM for user %s: %s", user_id, e)
