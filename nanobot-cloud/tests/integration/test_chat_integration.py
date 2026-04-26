"""
Integration tests: /chat endpoints.

NOTE: Firecracker VM tests are skipped — /dev/kvm not available.
We test everything except actual VM spin-up:
  - /chat/status returns "stopped" (no VM running)
  - /chat/stop is idempotent
  - /chat unauthenticated → 401/403
  - /admin/vms reflects empty pool
"""

import pytest


async def test_chat_status_no_vm_is_stopped(authed):
    client, _ = authed
    r = await client.get("/chat/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "stopped"


async def test_chat_stop_when_no_vm_is_ok(authed):
    client, _ = authed
    r = await client.post("/chat/stop")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


async def test_chat_stop_is_idempotent(authed):
    client, _ = authed
    r1 = await client.post("/chat/stop")
    r2 = await client.post("/chat/stop")
    assert r1.status_code == 200
    assert r2.status_code == 200


async def test_chat_status_unauthenticated(http):
    r = await http.get("/chat/status")
    assert r.status_code in (401, 403)


async def test_chat_stop_unauthenticated(http):
    r = await http.post("/chat/stop")
    assert r.status_code in (401, 403)


async def test_admin_vms_empty_when_no_vms(http):
    r = await http.get("/admin/vms")
    assert r.status_code == 200
    assert r.json() == []


async def test_different_users_have_separate_vm_status(authed, http):
    """Two different users both report 'stopped' independently."""
    client1, _ = authed

    import uuid
    u2 = f"vm2_{uuid.uuid4().hex[:8]}"
    await http.post("/users/register", json={"username": u2, "password": "pw"})
    r = await http.post("/users/login", json={"username": u2, "password": "pw"})
    token2 = r.json()["access_token"]

    import httpx as _httpx
    async with _httpx.AsyncClient(
        base_url=str(client1.base_url),
        headers={"Authorization": f"Bearer {token2}"},
        timeout=15,
    ) as client2:
        r1 = await client1.get("/chat/status")
        r2 = await client2.get("/chat/status")

    assert r1.json()["status"] == "stopped"
    assert r2.json()["status"] == "stopped"
