"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import chat, config, users
from scheduler.idle_reaper import IdleReaper
from settings import settings
from storage.db import async_session_factory, engine
from storage.models import Base
from storage.s3 import ensure_bucket
from vm.manager import init_manager

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables (idempotent; production should use Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await ensure_bucket()

    manager = init_manager(async_session_factory)
    reaper = IdleReaper(manager)
    reaper.start()
    app.state.manager = manager
    app.state.reaper = reaper

    log.info("nanobot-cloud started")
    yield

    reaper.stop()
    # Gracefully stop all VMs, persisting memory
    for user_id in list(manager.active_vms.keys()):
        try:
            await manager.stop(user_id, persist=True)
        except Exception as e:
            log.warning("error stopping VM on shutdown", user_id=str(user_id), error=str(e))

    await engine.dispose()
    log.info("nanobot-cloud stopped")


app = FastAPI(
    title="Nanobot Cloud",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(config.router)
app.include_router(chat.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/admin/vms")
async def admin_vms():
    """List all running VMs (no auth — restrict at infra level)."""
    from datetime import datetime, timezone
    manager = app.state.manager
    return [
        {
            "user_id": str(uid),
            "vm_id": vm.vm_id,
            "task_count": vm.task_count,
            "idle_seconds": (datetime.now(timezone.utc) - vm.last_active).total_seconds(),
        }
        for uid, vm in manager.active_vms.items()
    ]
