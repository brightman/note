"""
Chat endpoint: forwards user messages to the user's Firecracker VM via vsock RPC.
Supports both request-response and server-sent events (SSE) streaming.
"""

import asyncio
import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.middleware.auth import current_user
from storage.models import User
from vm.manager import get_manager

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    stream: bool = False
    model: str | None = None


@router.post("")
async def chat(
    body: ChatRequest,
    user: User = Depends(current_user),
):
    manager = get_manager()
    payload = {
        "messages": [m.model_dump() for m in body.messages],
        "stream": body.stream,
    }
    if body.model:
        payload["model"] = body.model

    if body.stream:
        return StreamingResponse(
            _stream_response(user.id, payload, manager),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    response = await manager.rpc(user.id, payload)
    return response


@router.get("/status")
async def vm_status(user: User = Depends(current_user)):
    manager = get_manager()
    vms = manager.active_vms
    vm = vms.get(user.id)
    if vm is None:
        return {"status": "stopped"}
    idle_seconds = None
    if vm.task_count == 0:
        from datetime import datetime, timezone
        idle_seconds = (datetime.now(timezone.utc) - vm.last_active).total_seconds()
    return {
        "status": "running",
        "vm_id": vm.vm_id,
        "task_count": vm.task_count,
        "idle_seconds": idle_seconds,
    }


@router.post("/stop")
async def stop_vm(user: User = Depends(current_user)):
    manager = get_manager()
    await manager.stop(user.id, persist=True)
    return {"ok": True}


async def _stream_response(
    user_id: uuid.UUID,
    payload: dict,
    manager,
) -> AsyncGenerator[str, None]:
    manager_ref = manager
    vm = await manager_ref.get_or_create(user_id)
    vm.task_count += 1
    from datetime import datetime, timezone
    vm.last_active = datetime.now(timezone.utc)
    try:
        from vm.vsock_client import VsockClient
        async with VsockClient(vm.vsock_path) as client:
            result = await client.rpc(payload)
        # Emit the full result as a single SSE event (nanobot doesn't stream natively yet)
        yield f"data: {json.dumps(result)}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    finally:
        vm.task_count -= 1
        vm.last_active = datetime.now(timezone.utc)
