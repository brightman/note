import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import create_token, current_user, hash_password, verify_password
from storage.db import get_session
from storage.models import AgentConfig, AgentPrompt, User

router = APIRouter(prefix="/users", tags=["users"])


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_session)):
    existing = await session.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already taken")

    user = User(
        id=uuid.uuid4(),
        username=body.username,
        hashed_password=hash_password(body.password),
    )
    default_config = AgentConfig(user_id=user.id, config={})
    default_prompt = AgentPrompt(
        id=uuid.uuid4(),
        user_id=user.id,
        prompt="You are a helpful personal AI assistant.",
        is_active=True,
    )
    session.add_all([user, default_config, default_prompt])
    await session.commit()
    return {"id": str(user.id), "username": user.username}


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=create_token(user.id))


@router.get("/me")
async def me(user: User = Depends(current_user)):
    return {"id": str(user.id), "username": user.username}
