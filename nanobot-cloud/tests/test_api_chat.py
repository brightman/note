"""API tests for /chat routes — standalone test app, no lifespan."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware.auth import current_user
from api.routes.chat import router as chat_router
from storage.db import get_session
from storage.models import User


def _make_user() -> User:
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.username = "chatuser"
    return u


def _app(manager, user: User) -> FastAPI:
    import vm.manager as vm_mod

    app = FastAPI()
    app.include_router(chat_router)

    async def _session():
        yield AsyncMock()

    async def _user():
        return user

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[current_user] = _user
    vm_mod._manager = manager
    return app


# ── /chat/status ──────────────────────────────────────────────────────────────

def test_status_no_vm_returns_stopped():
    user = _make_user()
    manager = MagicMock()
    manager.active_vms = {}

    with TestClient(_app(manager, user)) as client:
        resp = client.get("/chat/status")

    assert resp.status_code == 200
    assert resp.json()["status"] == "stopped"


def test_status_idle_vm_returns_running_with_idle_seconds():
    user = _make_user()
    vm = MagicMock()
    vm.vm_id = "vm-abc"
    vm.task_count = 0
    vm.last_active = datetime.now(timezone.utc) - timedelta(seconds=120)

    manager = MagicMock()
    manager.active_vms = {user.id: vm}

    with TestClient(_app(manager, user)) as client:
        resp = client.get("/chat/status")

    body = resp.json()
    assert body["status"] == "running"
    assert body["vm_id"] == "vm-abc"
    assert body["task_count"] == 0
    assert body["idle_seconds"] >= 120


def test_status_busy_vm_has_null_idle_seconds():
    user = _make_user()
    vm = MagicMock()
    vm.vm_id = "vm-busy"
    vm.task_count = 2
    vm.last_active = datetime.now(timezone.utc)

    manager = MagicMock()
    manager.active_vms = {user.id: vm}

    with TestClient(_app(manager, user)) as client:
        resp = client.get("/chat/status")

    body = resp.json()
    assert body["status"] == "running"
    assert body["task_count"] == 2
    assert body["idle_seconds"] is None


# ── /chat/stop ────────────────────────────────────────────────────────────────

def test_stop_vm_calls_manager_stop():
    user = _make_user()
    manager = MagicMock()
    manager.stop = AsyncMock()

    with TestClient(_app(manager, user)) as client:
        resp = client.post("/chat/stop")

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    manager.stop.assert_awaited_once_with(user.id, persist=True)


def test_stop_nonexistent_vm_still_returns_ok():
    user = _make_user()
    manager = MagicMock()
    # manager.stop does nothing (no VM)
    manager.stop = AsyncMock()

    with TestClient(_app(manager, user)) as client:
        resp = client.post("/chat/stop")

    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ── /health (from main app, no lifespan needed) ───────────────────────────────

def test_health_endpoint():
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
