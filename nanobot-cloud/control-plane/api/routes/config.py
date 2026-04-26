"""CRUD for agent config, system prompt, skills, and MCP servers."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import current_user
from config.crypto import encrypt_env
from storage.db import get_session
from storage.models import AgentConfig, AgentPrompt, User, UserMcpServer, UserSkill

router = APIRouter(prefix="/config", tags=["config"])


# ── Agent base config ────────────────────────────────────────────────────────

class ConfigBody(BaseModel):
    config: dict[str, Any]


@router.get("/agent")
async def get_agent_config(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(AgentConfig).where(AgentConfig.user_id == user.id)
    )
    row = result.scalar_one_or_none()
    return {"config": row.config if row else {}}


@router.put("/agent")
async def upsert_agent_config(
    body: ConfigBody,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(AgentConfig).where(AgentConfig.user_id == user.id)
    )
    row = result.scalar_one_or_none()
    if row:
        row.config = body.config
    else:
        session.add(AgentConfig(user_id=user.id, config=body.config))
    await session.commit()
    return {"ok": True}


# ── System prompt ────────────────────────────────────────────────────────────

class PromptBody(BaseModel):
    prompt: str


@router.get("/prompt")
async def get_prompt(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(AgentPrompt)
        .where(AgentPrompt.user_id == user.id, AgentPrompt.is_active.is_(True))
        .order_by(AgentPrompt.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return {"prompt": row.prompt if row else ""}


@router.put("/prompt")
async def set_prompt(
    body: PromptBody,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    # Deactivate old prompts
    old = await session.execute(
        select(AgentPrompt).where(AgentPrompt.user_id == user.id, AgentPrompt.is_active.is_(True))
    )
    for p in old.scalars():
        p.is_active = False

    session.add(
        AgentPrompt(id=uuid.uuid4(), user_id=user.id, prompt=body.prompt, is_active=True)
    )
    await session.commit()
    return {"ok": True}


# ── Skills ───────────────────────────────────────────────────────────────────

class SkillBody(BaseModel):
    name: str
    content: str
    skill_type: str = "markdown"


@router.get("/skills")
async def list_skills(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(UserSkill).where(UserSkill.user_id == user.id).order_by(UserSkill.name)
    )
    return [
        {"id": str(s.id), "name": s.name, "skill_type": s.skill_type, "enabled": s.enabled}
        for s in result.scalars()
    ]


@router.post("/skills", status_code=status.HTTP_201_CREATED)
async def create_skill(
    body: SkillBody,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    existing = await session.execute(
        select(UserSkill).where(UserSkill.user_id == user.id, UserSkill.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Skill name already exists")
    skill = UserSkill(
        id=uuid.uuid4(),
        user_id=user.id,
        name=body.name,
        content=body.content,
        skill_type=body.skill_type,
    )
    session.add(skill)
    await session.commit()
    return {"id": str(skill.id)}


@router.put("/skills/{skill_id}")
async def update_skill(
    skill_id: uuid.UUID,
    body: SkillBody,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(UserSkill).where(UserSkill.id == skill_id, UserSkill.user_id == user.id)
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    skill.name = body.name
    skill.content = body.content
    skill.skill_type = body.skill_type
    await session.commit()
    return {"ok": True}


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(UserSkill).where(UserSkill.id == skill_id, UserSkill.user_id == user.id)
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    await session.delete(skill)
    await session.commit()


# ── MCP Servers ──────────────────────────────────────────────────────────────

class McpBody(BaseModel):
    name: str
    command: str | None = None
    args: list[str] | None = None
    url: str | None = None
    env: dict[str, str] | None = None


@router.get("/mcp")
async def list_mcp(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(UserMcpServer).where(UserMcpServer.user_id == user.id)
    )
    return [
        {
            "id": str(m.id),
            "name": m.name,
            "command": m.command,
            "args": m.args,
            "url": m.url,
            "enabled": m.enabled,
        }
        for m in result.scalars()
    ]


@router.post("/mcp", status_code=status.HTTP_201_CREATED)
async def create_mcp(
    body: McpBody,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    if not body.command and not body.url:
        raise HTTPException(status_code=422, detail="Provide either command or url")
    existing = await session.execute(
        select(UserMcpServer).where(UserMcpServer.user_id == user.id, UserMcpServer.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="MCP server name already exists")

    mcp = UserMcpServer(
        id=uuid.uuid4(),
        user_id=user.id,
        name=body.name,
        command=body.command,
        args=body.args,
        url=body.url,
        env_encrypted=encrypt_env(body.env) if body.env else None,
    )
    session.add(mcp)
    await session.commit()
    return {"id": str(mcp.id)}


@router.delete("/mcp/{mcp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp(
    mcp_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(UserMcpServer).where(UserMcpServer.id == mcp_id, UserMcpServer.user_id == user.id)
    )
    mcp = result.scalar_one_or_none()
    if not mcp:
        raise HTTPException(status_code=404, detail="MCP server not found")
    await session.delete(mcp)
    await session.commit()
