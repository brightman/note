"""Assembles a complete nanobot config.json for a given user from DB records."""

import copy
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.crypto import decrypt_env
from storage.models import AgentConfig, AgentPrompt, UserMcpServer, UserSkill


async def build_nanobot_config(user_id: uuid.UUID, session: AsyncSession) -> dict[str, Any]:
    """Return a dict ready to be serialised as ~/.nanobot/config.json."""

    base_config = await _load_base_config(user_id, session)
    prompt = await _load_active_prompt(user_id, session)
    mcp_servers = await _load_mcp_servers(user_id, session)

    config = copy.deepcopy(base_config)

    # Inject system prompt
    config.setdefault("agents", {}).setdefault("defaults", {})
    if prompt:
        config["agents"]["defaults"]["systemPrompt"] = prompt

    # Inject MCP servers (merges with any already in base config)
    config.setdefault("mcpServers", {})
    config["mcpServers"].update(mcp_servers)

    return config


async def load_skills(user_id: uuid.UUID, session: AsyncSession) -> list[dict[str, str]]:
    """Return list of {name, content, skill_type} for enabled skills."""
    result = await session.execute(
        select(UserSkill)
        .where(UserSkill.user_id == user_id, UserSkill.enabled.is_(True))
        .order_by(UserSkill.name)
    )
    return [
        {"name": s.name, "content": s.content, "skill_type": s.skill_type}
        for s in result.scalars()
    ]


# ── helpers ──────────────────────────────────────────────────────────────────

async def _load_base_config(user_id: uuid.UUID, session: AsyncSession) -> dict:
    result = await session.execute(
        select(AgentConfig).where(AgentConfig.user_id == user_id)
    )
    row = result.scalar_one_or_none()
    return dict(row.config) if row else {}


async def _load_active_prompt(user_id: uuid.UUID, session: AsyncSession) -> str | None:
    result = await session.execute(
        select(AgentPrompt)
        .where(AgentPrompt.user_id == user_id, AgentPrompt.is_active.is_(True))
        .order_by(AgentPrompt.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row.prompt if row else None


async def _load_mcp_servers(
    user_id: uuid.UUID, session: AsyncSession
) -> dict[str, Any]:
    result = await session.execute(
        select(UserMcpServer)
        .where(UserMcpServer.user_id == user_id, UserMcpServer.enabled.is_(True))
    )
    servers: dict[str, Any] = {}
    for m in result.scalars():
        entry: dict[str, Any] = {}
        if m.command:
            entry["command"] = m.command
            entry["args"] = m.args or []
        elif m.url:
            entry["url"] = m.url
        if m.env_encrypted:
            entry["env"] = decrypt_env(m.env_encrypted)
        servers[m.name] = entry
    return servers


def config_to_bytes(config: dict) -> bytes:
    return json.dumps(config, indent=2, ensure_ascii=False).encode()
