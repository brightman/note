"""Unit tests for IdleReaper logic."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "control-plane"))

import pytest

with patch.dict(os.environ, {
    "NC_DATABASE_URL": "postgresql+asyncpg://x:x@localhost/x",
    "NC_ENCRYPTION_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==",
    "NC_VM_IDLE_TIMEOUT": "1800",
    "NC_VM_REAPER_INTERVAL": "60",
}):
    from scheduler.idle_reaper import IdleReaper
    from vm.manager import VMState


def _make_vm(user_id, idle_seconds, task_count=0):
    vm = MagicMock(spec=VMState)
    vm.user_id = user_id
    vm.vm_id = f"vm-{str(user_id)[:8]}"
    vm.task_count = task_count
    vm.last_active = datetime.now(timezone.utc) - timedelta(seconds=idle_seconds)
    return vm


@pytest.mark.asyncio
async def test_reaper_stops_idle_vm():
    uid = uuid.uuid4()
    vm = _make_vm(uid, idle_seconds=1900)  # > 1800s

    manager = MagicMock()
    manager.active_vms = {uid: vm}
    manager.stop = AsyncMock()

    reaper = IdleReaper(manager)
    await reaper._reap_once()

    manager.stop.assert_awaited_once_with(uid, persist=True)


@pytest.mark.asyncio
async def test_reaper_skips_active_vm():
    uid = uuid.uuid4()
    vm = _make_vm(uid, idle_seconds=1900, task_count=1)  # busy

    manager = MagicMock()
    manager.active_vms = {uid: vm}
    manager.stop = AsyncMock()

    reaper = IdleReaper(manager)
    await reaper._reap_once()

    manager.stop.assert_not_awaited()


@pytest.mark.asyncio
async def test_reaper_skips_recently_active_vm():
    uid = uuid.uuid4()
    vm = _make_vm(uid, idle_seconds=60)  # only 1 minute idle

    manager = MagicMock()
    manager.active_vms = {uid: vm}
    manager.stop = AsyncMock()

    reaper = IdleReaper(manager)
    await reaper._reap_once()

    manager.stop.assert_not_awaited()
