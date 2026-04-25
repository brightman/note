"""API tests for /users routes — standalone test app, no DB/lifespan."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware.auth import create_token, hash_password
from api.routes.users import router as users_router
from storage.db import get_session
from storage.models import AgentConfig, AgentPrompt, User


# ── test app factory ──────────────────────────────────────────────────────────

def _make_app(session: AsyncMock) -> FastAPI:
    app = FastAPI()
    app.include_router(users_router)

    async def _session():
        yield session

    app.dependency_overrides[get_session] = _session
    return app


def _empty_session() -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)
    session.add_all = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


def _session_with_user(user: User) -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    return session


# ── register ──────────────────────────────────────────────────────────────────

def test_register_success():
    app = _make_app(_empty_session())
    with TestClient(app) as client:
        resp = client.post("/users/register", json={"username": "alice", "password": "secret"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "alice"
    assert "id" in body


def test_register_duplicate_returns_409():
    existing = MagicMock(spec=User)
    existing.username = "alice"
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    session.execute = AsyncMock(return_value=result)

    app = _make_app(session)
    with TestClient(app) as client:
        resp = client.post("/users/register", json={"username": "alice", "password": "pw"})
    assert resp.status_code == 409


def test_register_creates_default_config_and_prompt():
    session = _empty_session()
    added_objects = []
    session.add_all = lambda objs: added_objects.extend(objs)

    app = _make_app(session)
    with TestClient(app) as client:
        client.post("/users/register", json={"username": "bob", "password": "pass"})

    # Should have added user + default config + default prompt
    assert len(added_objects) == 3
    types = {type(o).__name__ for o in added_objects}
    assert "User" in types or any(hasattr(o, "username") for o in added_objects)


# ── login ─────────────────────────────────────────────────────────────────────

def test_login_success():
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "alice"
    user.hashed_password = hash_password("correct")

    app = _make_app(_session_with_user(user))
    with TestClient(app) as client:
        resp = client.post("/users/login", json={"username": "alice", "password": "correct"})

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password_returns_401():
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.hashed_password = hash_password("correct")

    app = _make_app(_session_with_user(user))
    with TestClient(app) as client:
        resp = client.post("/users/login", json={"username": "alice", "password": "wrong"})

    assert resp.status_code == 401


def test_login_nonexistent_user_returns_401():
    app = _make_app(_empty_session())
    with TestClient(app) as client:
        resp = client.post("/users/login", json={"username": "ghost", "password": "pw"})
    assert resp.status_code == 401


def test_login_token_is_valid_jwt():
    from jose import jwt
    from settings import settings

    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.hashed_password = hash_password("pass")

    app = _make_app(_session_with_user(user))
    with TestClient(app) as client:
        resp = client.post("/users/login", json={"username": "u", "password": "pass"})

    token = resp.json()["access_token"]
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == str(user.id)


# ── /me ───────────────────────────────────────────────────────────────────────

def test_me_returns_user_info():
    from api.middleware.auth import current_user

    target_user = MagicMock(spec=User)
    target_user.id = uuid.uuid4()
    target_user.username = "alice"

    app = FastAPI()
    app.include_router(users_router)

    async def _user():
        return target_user

    async def _session():
        yield _empty_session()

    app.dependency_overrides[current_user] = _user
    app.dependency_overrides[get_session] = _session

    with TestClient(app) as client:
        resp = client.get("/users/me")

    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"
    assert resp.json()["id"] == str(target_user.id)


def test_me_without_token_returns_403_or_422():
    app = FastAPI()
    app.include_router(users_router)

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/users/me")

    assert resp.status_code in (401, 403, 422)
