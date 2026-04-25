"""API tests for /config routes — standalone test app, no lifespan."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware.auth import current_user
from api.routes.config import router as config_router
from storage.db import get_session
from storage.models import AgentConfig, AgentPrompt, User, UserMcpServer, UserSkill


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_user() -> User:
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.username = "testuser"
    return u


def _none_result() -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = None
    r.scalars.return_value = iter([])
    return r


def _one_result(obj) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = obj
    r.scalars.return_value = iter([obj])
    return r


def _many_result(objs: list) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = objs[0] if objs else None
    r.scalars.return_value = iter(objs)
    return r


def _app(session_fn, user: User) -> FastAPI:
    app = FastAPI()
    app.include_router(config_router)

    async def _get_session():
        yield session_fn()

    async def _current_user():
        return user

    app.dependency_overrides[get_session] = _get_session
    app.dependency_overrides[current_user] = _current_user
    return app


def _empty_session() -> AsyncMock:
    s = AsyncMock()
    s.execute = AsyncMock(return_value=_none_result())
    s.add = MagicMock()
    s.delete = AsyncMock()
    s.commit = AsyncMock()
    return s


# ── agent config ──────────────────────────────────────────────────────────────

def test_get_agent_config_no_row_returns_empty():
    user = _make_user()
    app = _app(lambda: _empty_session(), user)
    with TestClient(app) as client:
        resp = client.get("/config/agent")
    assert resp.status_code == 200
    assert resp.json()["config"] == {}


def test_get_agent_config_returns_stored():
    user = _make_user()
    row = MagicMock(spec=AgentConfig)
    row.config = {"providers": {"openai": {"apiKey": "sk-x"}}}

    def _sess():
        s = AsyncMock()
        s.execute = AsyncMock(return_value=_one_result(row))
        s.commit = AsyncMock()
        return s

    app = _app(_sess, user)
    with TestClient(app) as client:
        resp = client.get("/config/agent")
    assert resp.json()["config"]["providers"]["openai"]["apiKey"] == "sk-x"


def test_put_agent_config_updates_existing_row():
    user = _make_user()
    existing = MagicMock(spec=AgentConfig)
    existing.config = {}

    def _sess():
        s = AsyncMock()
        s.execute = AsyncMock(return_value=_one_result(existing))
        s.commit = AsyncMock()
        return s

    app = _app(_sess, user)
    with TestClient(app) as client:
        resp = client.put("/config/agent", json={"config": {"model": "gpt-4o"}})
    assert resp.status_code == 200
    assert existing.config == {"model": "gpt-4o"}


def test_put_agent_config_creates_if_no_row():
    user = _make_user()
    added = []

    def _sess():
        s = AsyncMock()
        s.execute = AsyncMock(return_value=_none_result())
        s.add = lambda x: added.append(x)
        s.commit = AsyncMock()
        return s

    app = _app(_sess, user)
    with TestClient(app) as client:
        client.put("/config/agent", json={"config": {"k": "v"}})
    assert len(added) == 1
    assert isinstance(added[0], AgentConfig)


# ── system prompt ─────────────────────────────────────────────────────────────

def test_get_prompt_no_row_returns_empty_string():
    user = _make_user()
    app = _app(lambda: _empty_session(), user)
    with TestClient(app) as client:
        resp = client.get("/config/prompt")
    assert resp.json() == {"prompt": ""}


def test_get_prompt_returns_active_prompt():
    user = _make_user()
    row = MagicMock(spec=AgentPrompt)
    row.prompt = "You are helpful."

    def _sess():
        s = AsyncMock()
        s.execute = AsyncMock(return_value=_one_result(row))
        s.commit = AsyncMock()
        return s

    app = _app(_sess, user)
    with TestClient(app) as client:
        resp = client.get("/config/prompt")
    assert resp.json()["prompt"] == "You are helpful."


def test_put_prompt_deactivates_old_creates_new():
    user = _make_user()
    old = MagicMock(spec=AgentPrompt)
    old.is_active = True
    added = []
    call_count = [0]

    def _sess():
        s = AsyncMock()

        async def execute(stmt):
            call_count[0] += 1
            # First call = fetch old active prompts, second = fetch new (for verification)
            if call_count[0] == 1:
                return _many_result([old])
            return _none_result()

        s.execute = execute
        s.add = lambda x: added.append(x)
        s.commit = AsyncMock()
        return s

    app = _app(_sess, user)
    with TestClient(app) as client:
        resp = client.put("/config/prompt", json={"prompt": "New prompt."})

    assert resp.status_code == 200
    assert old.is_active is False
    assert len(added) == 1
    assert isinstance(added[0], AgentPrompt)
    assert added[0].prompt == "New prompt."


# ── skills ────────────────────────────────────────────────────────────────────

def test_list_skills_empty():
    user = _make_user()

    def _sess():
        s = AsyncMock()
        r = MagicMock()
        r.scalars.return_value = iter([])
        s.execute = AsyncMock(return_value=r)
        return s

    app = _app(_sess, user)
    with TestClient(app) as client:
        resp = client.get("/config/skills")
    assert resp.json() == []


def test_list_skills_returns_metadata():
    user = _make_user()
    skill = MagicMock(spec=UserSkill)
    skill.id = uuid.uuid4()
    skill.name = "write_file"
    skill.skill_type = "markdown"
    skill.enabled = True

    def _sess():
        s = AsyncMock()
        r = MagicMock()
        r.scalars.return_value = iter([skill])
        s.execute = AsyncMock(return_value=r)
        return s

    app = _app(_sess, user)
    with TestClient(app) as client:
        resp = client.get("/config/skills")

    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "write_file"


def test_create_skill_success():
    user = _make_user()
    added = []

    def _sess():
        s = AsyncMock()
        s.execute = AsyncMock(return_value=_none_result())
        s.add = lambda x: added.append(x)
        s.commit = AsyncMock()
        return s

    app = _app(_sess, user)
    with TestClient(app) as client:
        resp = client.post("/config/skills", json={
            "name": "write_file",
            "content": "# write a file\n...",
            "skill_type": "markdown",
        })

    assert resp.status_code == 201
    assert "id" in resp.json()
    assert len(added) == 1


def test_create_skill_duplicate_409():
    user = _make_user()
    existing = MagicMock(spec=UserSkill)
    existing.name = "write_file"

    def _sess():
        s = AsyncMock()
        s.execute = AsyncMock(return_value=_one_result(existing))
        return s

    app = _app(_sess, user)
    with TestClient(app) as client:
        resp = client.post("/config/skills", json={"name": "write_file", "content": "..."})
    assert resp.status_code == 409


def test_update_skill_success():
    user = _make_user()
    skill = MagicMock(spec=UserSkill)
    skill.id = uuid.uuid4()
    skill.name = "old_name"
    skill.content = "old content"
    skill.skill_type = "markdown"

    def _sess():
        s = AsyncMock()
        s.execute = AsyncMock(return_value=_one_result(skill))
        s.commit = AsyncMock()
        return s

    app = _app(_sess, user)
    with TestClient(app) as client:
        resp = client.put(f"/config/skills/{skill.id}", json={
            "name": "new_name",
            "content": "new content",
            "skill_type": "python",
        })

    assert resp.status_code == 200
    assert skill.name == "new_name"
    assert skill.content == "new content"
    assert skill.skill_type == "python"


def test_update_skill_not_found_404():
    user = _make_user()
    app = _app(lambda: _empty_session(), user)
    with TestClient(app) as client:
        resp = client.put(f"/config/skills/{uuid.uuid4()}", json={
            "name": "x", "content": "y", "skill_type": "markdown"
        })
    assert resp.status_code == 404


def test_delete_skill_success():
    user = _make_user()
    skill = MagicMock(spec=UserSkill)
    skill.id = uuid.uuid4()
    deleted = []

    def _sess():
        s = AsyncMock()
        s.execute = AsyncMock(return_value=_one_result(skill))
        s.delete = AsyncMock(side_effect=lambda x: deleted.append(x))
        s.commit = AsyncMock()
        return s

    app = _app(_sess, user)
    with TestClient(app) as client:
        resp = client.delete(f"/config/skills/{skill.id}")
    assert resp.status_code == 204
    assert len(deleted) == 1


def test_delete_skill_not_found_404():
    user = _make_user()
    app = _app(lambda: _empty_session(), user)
    with TestClient(app) as client:
        resp = client.delete(f"/config/skills/{uuid.uuid4()}")
    assert resp.status_code == 404


# ── MCP servers ───────────────────────────────────────────────────────────────

def test_list_mcp_empty():
    user = _make_user()

    def _sess():
        s = AsyncMock()
        r = MagicMock()
        r.scalars.return_value = iter([])
        s.execute = AsyncMock(return_value=r)
        return s

    app = _app(_sess, user)
    with TestClient(app) as client:
        resp = client.get("/config/mcp")
    assert resp.json() == []


def test_create_mcp_no_command_no_url_returns_422():
    user = _make_user()
    app = _app(lambda: _empty_session(), user)
    with TestClient(app) as client:
        resp = client.post("/config/mcp", json={"name": "bad"})
    assert resp.status_code == 422


def test_create_mcp_stdio_success():
    user = _make_user()
    added = []

    def _sess():
        s = AsyncMock()
        s.execute = AsyncMock(return_value=_none_result())
        s.add = lambda x: added.append(x)
        s.commit = AsyncMock()
        return s

    app = _app(_sess, user)
    with TestClient(app) as client:
        resp = client.post("/config/mcp", json={
            "name": "github",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_TOKEN": "ghp_xxx"},
        })
    assert resp.status_code == 201
    assert len(added) == 1
    # env should be encrypted in the stored object
    assert added[0].env_encrypted is not None


def test_create_mcp_http_success():
    user = _make_user()
    added = []

    def _sess():
        s = AsyncMock()
        s.execute = AsyncMock(return_value=_none_result())
        s.add = lambda x: added.append(x)
        s.commit = AsyncMock()
        return s

    app = _app(_sess, user)
    with TestClient(app) as client:
        resp = client.post("/config/mcp", json={
            "name": "remote",
            "url": "https://mcp.example.com/v1",
        })
    assert resp.status_code == 201
    assert added[0].url == "https://mcp.example.com/v1"
    assert added[0].env_encrypted is None


def test_create_mcp_duplicate_409():
    user = _make_user()
    existing = MagicMock(spec=UserMcpServer)

    def _sess():
        s = AsyncMock()
        s.execute = AsyncMock(return_value=_one_result(existing))
        return s

    app = _app(_sess, user)
    with TestClient(app) as client:
        resp = client.post("/config/mcp", json={"name": "dup", "command": "cmd"})
    assert resp.status_code == 409


def test_delete_mcp_success():
    user = _make_user()
    mcp = MagicMock(spec=UserMcpServer)
    mcp.id = uuid.uuid4()
    deleted = []

    def _sess():
        s = AsyncMock()
        s.execute = AsyncMock(return_value=_one_result(mcp))
        s.delete = AsyncMock(side_effect=lambda x: deleted.append(x))
        s.commit = AsyncMock()
        return s

    app = _app(_sess, user)
    with TestClient(app) as client:
        resp = client.delete(f"/config/mcp/{mcp.id}")
    assert resp.status_code == 204
    assert len(deleted) == 1


def test_delete_mcp_not_found_404():
    user = _make_user()
    app = _app(lambda: _empty_session(), user)
    with TestClient(app) as client:
        resp = client.delete(f"/config/mcp/{uuid.uuid4()}")
    assert resp.status_code == 404
