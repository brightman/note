"""Integration tests: agent config, prompt, skills, MCP — real DB."""

import uuid
import pytest


# ── agent config ──────────────────────────────────────────────────────────────

async def test_agent_config_default_is_empty(authed):
    client, _ = authed
    r = await client.get("/config/agent")
    assert r.status_code == 200
    assert r.json()["config"] == {}


async def test_agent_config_put_and_get(authed):
    client, _ = authed
    payload = {
        "providers": {"openrouter": {"apiKey": "sk-test-123"}},
        "agents": {"defaults": {"model": "anthropic/claude-opus-4-6"}},
    }
    r = await client.put("/config/agent", json={"config": payload})
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    r = await client.get("/config/agent")
    stored = r.json()["config"]
    assert stored["providers"]["openrouter"]["apiKey"] == "sk-test-123"
    assert stored["agents"]["defaults"]["model"] == "anthropic/claude-opus-4-6"


async def test_agent_config_update_overwrites(authed):
    client, _ = authed
    await client.put("/config/agent", json={"config": {"key": "v1"}})
    await client.put("/config/agent", json={"config": {"key": "v2", "extra": "added"}})
    r = await client.get("/config/agent")
    cfg = r.json()["config"]
    assert cfg["key"] == "v2"
    assert cfg["extra"] == "added"


async def test_configs_are_isolated_per_user(authed, http):
    client1, _ = authed
    await client1.put("/config/agent", json={"config": {"user": "one"}})

    # Create a second user and check they have separate config
    u2 = f"cfg_{uuid.uuid4().hex[:8]}"
    await http.post("/users/register", json={"username": u2, "password": "pw"})
    r = await http.post("/users/login", json={"username": u2, "password": "pw"})
    token2 = r.json()["access_token"]

    import httpx as _httpx
    async with _httpx.AsyncClient(
        base_url=str(client1.base_url),
        headers={"Authorization": f"Bearer {token2}"},
        timeout=15,
    ) as client2:
        r2 = await client2.get("/config/agent")
        # User 2 should NOT see user 1's config
        assert r2.json()["config"] != {"user": "one"}


# ── system prompt ─────────────────────────────────────────────────────────────

async def test_prompt_default_is_nonempty(authed):
    client, _ = authed
    r = await client.get("/config/prompt")
    assert r.status_code == 200
    assert len(r.json()["prompt"]) > 0


async def test_prompt_put_and_get(authed):
    client, _ = authed
    new_prompt = "You are a concise assistant. Reply in bullet points."
    r = await client.put("/config/prompt", json={"prompt": new_prompt})
    assert r.status_code == 200

    r = await client.get("/config/prompt")
    assert r.json()["prompt"] == new_prompt


async def test_prompt_update_replaces_active(authed):
    client, _ = authed
    await client.put("/config/prompt", json={"prompt": "First prompt."})
    await client.put("/config/prompt", json={"prompt": "Second prompt."})
    r = await client.get("/config/prompt")
    assert r.json()["prompt"] == "Second prompt."


# ── skills ────────────────────────────────────────────────────────────────────

async def test_skills_list_initially_empty(authed):
    client, _ = authed
    r = await client.get("/config/skills")
    assert r.status_code == 200
    assert r.json() == []


async def test_skill_create_and_list(authed):
    client, _ = authed
    r = await client.post("/config/skills", json={
        "name": "write_file",
        "content": "# Write a file\nUse the write_file tool to create files.",
        "skill_type": "markdown",
    })
    assert r.status_code == 201
    skill_id = r.json()["id"]
    uuid.UUID(skill_id)

    r = await client.get("/config/skills")
    skills = r.json()
    assert len(skills) == 1
    assert skills[0]["name"] == "write_file"
    assert skills[0]["skill_type"] == "markdown"
    assert skills[0]["enabled"] is True


async def test_skill_create_duplicate_returns_409(authed):
    client, _ = authed
    await client.post("/config/skills", json={"name": "s1", "content": "c", "skill_type": "markdown"})
    r = await client.post("/config/skills", json={"name": "s1", "content": "c2", "skill_type": "markdown"})
    assert r.status_code == 409


async def test_skill_update(authed):
    client, _ = authed
    r = await client.post("/config/skills", json={"name": "orig", "content": "old", "skill_type": "markdown"})
    sid = r.json()["id"]

    r = await client.put(f"/config/skills/{sid}", json={
        "name": "updated",
        "content": "new content",
        "skill_type": "python",
    })
    assert r.status_code == 200

    r = await client.get("/config/skills")
    s = r.json()[0]
    assert s["name"] == "updated"
    assert s["skill_type"] == "python"


async def test_skill_delete(authed):
    client, _ = authed
    r = await client.post("/config/skills", json={"name": "todel", "content": "x", "skill_type": "markdown"})
    sid = r.json()["id"]

    r = await client.delete(f"/config/skills/{sid}")
    assert r.status_code == 204

    r = await client.get("/config/skills")
    assert r.json() == []


async def test_skill_update_not_found(authed):
    client, _ = authed
    r = await client.put(f"/config/skills/{uuid.uuid4()}", json={
        "name": "x", "content": "y", "skill_type": "markdown"
    })
    assert r.status_code == 404


async def test_skill_delete_not_found(authed):
    client, _ = authed
    r = await client.delete(f"/config/skills/{uuid.uuid4()}")
    assert r.status_code == 404


async def test_multiple_skills(authed):
    client, _ = authed
    for i in range(3):
        await client.post("/config/skills", json={
            "name": f"skill_{i}",
            "content": f"content {i}",
            "skill_type": "markdown",
        })
    r = await client.get("/config/skills")
    assert len(r.json()) == 3
    names = {s["name"] for s in r.json()}
    assert names == {"skill_0", "skill_1", "skill_2"}


# ── MCP servers ───────────────────────────────────────────────────────────────

async def test_mcp_list_initially_empty(authed):
    client, _ = authed
    r = await client.get("/config/mcp")
    assert r.status_code == 200
    assert r.json() == []


async def test_mcp_create_stdio(authed):
    client, _ = authed
    r = await client.post("/config/mcp", json={
        "name": "github",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_TOKEN": "ghp_secret_token"},
    })
    assert r.status_code == 201
    mcp_id = r.json()["id"]
    uuid.UUID(mcp_id)

    r = await client.get("/config/mcp")
    mcps = r.json()
    assert len(mcps) == 1
    m = mcps[0]
    assert m["name"] == "github"
    assert m["command"] == "npx"
    assert m["enabled"] is True
    # env should NOT be exposed in the list response
    assert "env" not in m
    assert "env_encrypted" not in m


async def test_mcp_create_http(authed):
    client, _ = authed
    r = await client.post("/config/mcp", json={
        "name": "remote_tool",
        "url": "https://mcp.example.com/v1",
    })
    assert r.status_code == 201

    r = await client.get("/config/mcp")
    m = r.json()[0]
    assert m["url"] == "https://mcp.example.com/v1"
    assert m["command"] is None


async def test_mcp_create_no_command_no_url_returns_422(authed):
    client, _ = authed
    r = await client.post("/config/mcp", json={"name": "bad"})
    assert r.status_code == 422


async def test_mcp_create_duplicate_returns_409(authed):
    client, _ = authed
    await client.post("/config/mcp", json={"name": "dup_mcp", "command": "cmd"})
    r = await client.post("/config/mcp", json={"name": "dup_mcp", "command": "cmd"})
    assert r.status_code == 409


async def test_mcp_delete(authed):
    client, _ = authed
    r = await client.post("/config/mcp", json={"name": "to_del", "command": "x"})
    mid = r.json()["id"]

    r = await client.delete(f"/config/mcp/{mid}")
    assert r.status_code == 204

    r = await client.get("/config/mcp")
    assert r.json() == []


async def test_mcp_delete_not_found(authed):
    client, _ = authed
    r = await client.delete(f"/config/mcp/{uuid.uuid4()}")
    assert r.status_code == 404


async def test_mcp_env_is_stored_encrypted_and_not_leaked(authed):
    """Env vars must not appear in list responses (only stored encrypted in DB)."""
    client, _ = authed
    await client.post("/config/mcp", json={
        "name": "secret_tool",
        "command": "secret-cmd",
        "env": {"SECRET_KEY": "super_secret_value"},
    })
    r = await client.get("/config/mcp")
    raw = r.text
    assert "super_secret_value" not in raw
    assert "SECRET_KEY" not in raw
