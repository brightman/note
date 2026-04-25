"""Additional idle reaper tests: boundary, multiple VMs, error resilience."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from scheduler.idle_reaper import IdleReaper
from vm.manager import VMState

TIMEOUT = 1800  # settings default


def _make_vm(idle_seconds: float, task_count: int = 0) -> MagicMock:
    vm = MagicMock(spec=VMState)
    vm.user_id = uuid.uuid4()
    vm.vm_id = f"vm-test"
    vm.task_count = task_count
    vm.last_active = datetime.now(timezone.utc) - timedelta(seconds=idle_seconds)
    return vm


def _manager(*vms) -> MagicMock:
    m = MagicMock()
    m.active_vms = {vm.user_id: vm for vm in vms}
    m.stop = AsyncMock()
    return m


# ── boundary conditions ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_exactly_at_timeout_is_stopped():
    vm = _make_vm(idle_seconds=TIMEOUT)
    manager = _manager(vm)
    await IdleReaper(manager)._reap_once()
    manager.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_one_second_before_timeout_is_not_stopped():
    vm = _make_vm(idle_seconds=TIMEOUT - 1)
    manager = _manager(vm)
    await IdleReaper(manager)._reap_once()
    manager.stop.assert_not_awaited()


@pytest.mark.asyncio
async def test_zero_idle_is_not_stopped():
    vm = _make_vm(idle_seconds=0)
    manager = _manager(vm)
    await IdleReaper(manager)._reap_once()
    manager.stop.assert_not_awaited()


# ── multiple VMs ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_only_idle_vms_stopped_among_many():
    idle1 = _make_vm(idle_seconds=2000)
    idle2 = _make_vm(idle_seconds=9000)
    active = _make_vm(idle_seconds=2000, task_count=2)
    fresh = _make_vm(idle_seconds=100)

    manager = _manager(idle1, idle2, active, fresh)
    await IdleReaper(manager)._reap_once()

    stopped_ids = {c.args[0] for c in manager.stop.call_args_list}
    assert idle1.user_id in stopped_ids
    assert idle2.user_id in stopped_ids
    assert active.user_id not in stopped_ids
    assert fresh.user_id not in stopped_ids


@pytest.mark.asyncio
async def test_empty_vm_pool_no_error():
    manager = MagicMock()
    manager.active_vms = {}
    manager.stop = AsyncMock()
    await IdleReaper(manager)._reap_once()
    manager.stop.assert_not_awaited()


# ── error resilience ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stop_error_does_not_abort_others():
    """If stopping vm1 raises, vm2 should still be stopped."""
    vm1 = _make_vm(idle_seconds=2000)
    vm2 = _make_vm(idle_seconds=3000)

    manager = _manager(vm1, vm2)
    stop_calls = []

    async def flaky_stop(user_id, *, persist):
        stop_calls.append(user_id)
        if user_id == vm1.user_id:
            raise RuntimeError("simulated stop failure")

    manager.stop = flaky_stop
    # Should not raise
    await IdleReaper(manager)._reap_once()
    assert len(stop_calls) == 2


# ── start/stop task lifecycle ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_creates_task_and_stop_cancels():
    manager = _manager()
    reaper = IdleReaper(manager)
    reaper.start()
    assert reaper._task is not None
    assert not reaper._task.done()
    reaper.stop()
    await asyncio.sleep(0)  # allow cancellation to propagate
    assert reaper._task.cancelled() or reaper._task.done()


@pytest.mark.asyncio
async def test_stop_without_start_is_safe():
    manager = _manager()
    reaper = IdleReaper(manager)
    reaper.stop()  # should not raise
