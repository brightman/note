"""Unit tests for config injector (no DB required — uses mocks)."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Patch settings before importing the module
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "control-plane"))

with patch.dict(os.environ, {
    "NC_DATABASE_URL": "postgresql+asyncpg://x:x@localhost/x",
    "NC_ENCRYPTION_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==",
}):
    from config.injector import build_nanobot_config, config_to_bytes


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalars(self):
        return iter(self._items)


def _make_session(base_cfg, active_prompt, mcp_servers, skills):
    session = AsyncMock()

    async def execute(stmt):
        # Determine which table is being queried by checking the model
        from storage.models import AgentConfig, AgentPrompt, UserMcpServer, UserSkill
        entity = stmt.column_descriptions[0]["entity"] if hasattr(stmt, "column_descriptions") else None
        # Simple dispatch based on the objects provided
        if base_cfg is not None and entity == AgentConfig:
            return _FakeResult([base_cfg])
        if active_prompt is not None and entity == AgentPrompt:
            return _FakeResult([active_prompt])
        if mcp_servers is not None and entity == UserMcpServer:
            return _FakeResult(mcp_servers)
        return _FakeResult([])

    session.execute = execute
    return session


@pytest.mark.asyncio
async def test_config_to_bytes_is_json():
    cfg = {"providers": {"openai": {"apiKey": "sk-test"}}}
    data = config_to_bytes(cfg)
    assert json.loads(data) == cfg


@pytest.mark.asyncio
async def test_build_injects_system_prompt():
    from storage.models import AgentConfig, AgentPrompt

    uid = uuid.uuid4()

    base = MagicMock(spec=AgentConfig)
    base.config = {"agents": {"defaults": {"model": "gpt-4o"}}}

    prompt = MagicMock(spec=AgentPrompt)
    prompt.prompt = "You are a coding assistant."

    session = AsyncMock()

    async def fake_execute(stmt):
        # Route by checking which model class is involved
        sql = str(stmt)
        if "agent_configs" in sql.lower():
            return _FakeResult([base])
        if "agent_prompts" in sql.lower():
            return _FakeResult([prompt])
        return _FakeResult([])

    session.execute = fake_execute

    cfg = await build_nanobot_config(uid, session)
    assert cfg["agents"]["defaults"]["systemPrompt"] == "You are a coding assistant."
    assert cfg["agents"]["defaults"]["model"] == "gpt-4o"
