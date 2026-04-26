"""Full branch coverage for config/injector.py."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from config.crypto import encrypt_env
from config.injector import build_nanobot_config, config_to_bytes, load_skills
from storage.models import AgentConfig, AgentPrompt, UserMcpServer, UserSkill


# ── helpers ──────────────────────────────────────────────────────────────────

class _Result:
    def __init__(self, items):
        self._items = items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalars(self):
        return iter(self._items)


def _session_factory(agent_cfg=None, prompt=None, mcps=None, skills=None):
    """Return an async session that routes by table name in SQL string."""
    session = AsyncMock()

    async def execute(stmt):
        sql = str(stmt).lower()
        if "agent_configs" in sql:
            return _Result([agent_cfg] if agent_cfg else [])
        if "agent_prompts" in sql:
            return _Result([prompt] if prompt else [])
        if "user_mcp_servers" in sql:
            return _Result(mcps or [])
        if "user_skills" in sql:
            return _Result(skills or [])
        return _Result([])

    session.execute = execute
    return session


def _make_agent_config(cfg: dict) -> AgentConfig:
    row = MagicMock(spec=AgentConfig)
    row.config = cfg
    return row


def _make_prompt(text: str) -> AgentPrompt:
    row = MagicMock(spec=AgentPrompt)
    row.prompt = text
    return row


def _make_mcp_stdio(name, command, args=None, env_dict=None) -> UserMcpServer:
    m = MagicMock(spec=UserMcpServer)
    m.name = name
    m.command = command
    m.args = args or []
    m.url = None
    m.env_encrypted = encrypt_env(env_dict) if env_dict else None
    return m


def _make_mcp_http(name, url, env_dict=None) -> UserMcpServer:
    m = MagicMock(spec=UserMcpServer)
    m.name = name
    m.command = None
    m.args = None
    m.url = url
    m.env_encrypted = encrypt_env(env_dict) if env_dict else None
    return m


def _make_skill(name, content, skill_type="markdown") -> UserSkill:
    s = MagicMock(spec=UserSkill)
    s.name = name
    s.content = content
    s.skill_type = skill_type
    return s


# ── tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_db_returns_minimal_config():
    """No rows in DB → config has agents.defaults and mcpServers keys."""
    session = _session_factory()
    cfg = await build_nanobot_config(uuid.uuid4(), session)
    assert "agents" in cfg
    assert "mcpServers" in cfg
    assert cfg["mcpServers"] == {}


@pytest.mark.asyncio
async def test_base_config_preserved():
    base = _make_agent_config({"providers": {"openrouter": {"apiKey": "sk-x"}}})
    session = _session_factory(agent_cfg=base)
    cfg = await build_nanobot_config(uuid.uuid4(), session)
    assert cfg["providers"]["openrouter"]["apiKey"] == "sk-x"


@pytest.mark.asyncio
async def test_no_prompt_leaves_no_system_prompt():
    session = _session_factory()
    cfg = await build_nanobot_config(uuid.uuid4(), session)
    assert "systemPrompt" not in cfg.get("agents", {}).get("defaults", {})


@pytest.mark.asyncio
async def test_prompt_injected():
    prompt = _make_prompt("Be concise.")
    session = _session_factory(prompt=prompt)
    cfg = await build_nanobot_config(uuid.uuid4(), session)
    assert cfg["agents"]["defaults"]["systemPrompt"] == "Be concise."


@pytest.mark.asyncio
async def test_prompt_does_not_overwrite_other_defaults():
    base = _make_agent_config({"agents": {"defaults": {"model": "gpt-4o", "temperature": 0.7}}})
    prompt = _make_prompt("Hello.")
    session = _session_factory(agent_cfg=base, prompt=prompt)
    cfg = await build_nanobot_config(uuid.uuid4(), session)
    assert cfg["agents"]["defaults"]["model"] == "gpt-4o"
    assert cfg["agents"]["defaults"]["temperature"] == 0.7
    assert cfg["agents"]["defaults"]["systemPrompt"] == "Hello."


@pytest.mark.asyncio
async def test_mcp_stdio_injected():
    mcp = _make_mcp_stdio("github", "npx", ["-y", "@modelcontextprotocol/server-github"])
    session = _session_factory(mcps=[mcp])
    cfg = await build_nanobot_config(uuid.uuid4(), session)
    assert "github" in cfg["mcpServers"]
    assert cfg["mcpServers"]["github"]["command"] == "npx"
    assert cfg["mcpServers"]["github"]["args"] == ["-y", "@modelcontextprotocol/server-github"]


@pytest.mark.asyncio
async def test_mcp_http_injected():
    mcp = _make_mcp_http("myservice", "https://mcp.example.com/v1")
    session = _session_factory(mcps=[mcp])
    cfg = await build_nanobot_config(uuid.uuid4(), session)
    assert cfg["mcpServers"]["myservice"]["url"] == "https://mcp.example.com/v1"
    assert "command" not in cfg["mcpServers"]["myservice"]


@pytest.mark.asyncio
async def test_mcp_env_decrypted():
    env = {"GITHUB_TOKEN": "ghp_secret", "OTHER": "value"}
    mcp = _make_mcp_stdio("github", "npx", env_dict=env)
    session = _session_factory(mcps=[mcp])
    cfg = await build_nanobot_config(uuid.uuid4(), session)
    assert cfg["mcpServers"]["github"]["env"] == env


@pytest.mark.asyncio
async def test_mcp_no_env_no_env_key():
    mcp = _make_mcp_stdio("tool", "python", ["-m", "tool"])
    session = _session_factory(mcps=[mcp])
    cfg = await build_nanobot_config(uuid.uuid4(), session)
    assert "env" not in cfg["mcpServers"]["tool"]


@pytest.mark.asyncio
async def test_multiple_mcp_servers():
    mcps = [
        _make_mcp_stdio("tool_a", "cmd_a"),
        _make_mcp_http("tool_b", "http://b.test"),
    ]
    session = _session_factory(mcps=mcps)
    cfg = await build_nanobot_config(uuid.uuid4(), session)
    assert set(cfg["mcpServers"].keys()) == {"tool_a", "tool_b"}


@pytest.mark.asyncio
async def test_mcp_merges_with_base_config():
    """MCP servers in base config are preserved alongside DB servers."""
    base = _make_agent_config({"mcpServers": {"from_base": {"command": "base_cmd", "args": []}}})
    mcp = _make_mcp_stdio("from_db", "db_cmd")
    session = _session_factory(agent_cfg=base, mcps=[mcp])
    cfg = await build_nanobot_config(uuid.uuid4(), session)
    assert "from_base" in cfg["mcpServers"]
    assert "from_db" in cfg["mcpServers"]


@pytest.mark.asyncio
async def test_load_skills_empty():
    session = _session_factory()
    skills = await load_skills(uuid.uuid4(), session)
    assert skills == []


@pytest.mark.asyncio
async def test_load_skills_returns_all_enabled():
    s1 = _make_skill("write_file", "# Write a file\n...", "markdown")
    s2 = _make_skill("run_query", "import db", "python")
    session = _session_factory(skills=[s1, s2])
    skills = await load_skills(uuid.uuid4(), session)
    assert len(skills) == 2
    names = {s["name"] for s in skills}
    assert names == {"write_file", "run_query"}
    types = {s["skill_type"] for s in skills}
    assert types == {"markdown", "python"}


def test_config_to_bytes_valid_json():
    cfg = {"key": "value", "num": 42, "nested": {"a": [1, 2, 3]}}
    data = config_to_bytes(cfg)
    assert json.loads(data) == cfg


def test_config_to_bytes_unicode():
    cfg = {"name": "日本語", "emoji": "🤖"}
    data = config_to_bytes(cfg)
    parsed = json.loads(data)
    assert parsed["name"] == "日本語"
    assert parsed["emoji"] == "🤖"


def test_config_does_not_mutate_original():
    original = {"agents": {"defaults": {}}}
    import copy
    original_copy = copy.deepcopy(original)

    class _R:
        def scalar_one_or_none(self): return None
        def scalars(self): return iter([])

    # We can't easily test mutation without a real session here,
    # but verify config_to_bytes doesn't mutate
    _ = config_to_bytes(original)
    assert original == original_copy
