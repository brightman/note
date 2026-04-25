"""Additional vsock tests: empty file, large payload, timeouts, wait_for_guest_ready."""

import asyncio
import json
import os
import struct
import tempfile

import pytest

from vm.vsock_client import VsockClient, wait_for_guest_ready

CMD_SEND_FILE = 0x01
CMD_FETCH_FILE = 0x02
CMD_RPC = 0x03
CMD_PING = 0xFF


# ── reusable echo server ──────────────────────────────────────────────────────

_STORED: dict[str, bytes] = {}


async def _stateful_server(reader, writer):
    """Server that stores sent files and returns them on fetch."""
    try:
        while True:
            cmd = struct.unpack("<I", await reader.readexactly(4))[0]

            if cmd == CMD_PING:
                writer.write(struct.pack("<I", CMD_PING))
                await writer.drain()

            elif cmd == CMD_SEND_FILE:
                nlen = struct.unpack("<I", await reader.readexactly(4))[0]
                name = (await reader.readexactly(nlen)).decode()
                dlen = struct.unpack("<Q", await reader.readexactly(8))[0]
                data = await reader.readexactly(dlen)
                _STORED[name] = data

            elif cmd == CMD_FETCH_FILE:
                nlen = struct.unpack("<I", await reader.readexactly(4))[0]
                name = (await reader.readexactly(nlen)).decode()
                data = _STORED.get(name, b"")
                writer.write(struct.pack("<Q", len(data)))
                writer.write(data)
                await writer.drain()

            elif cmd == CMD_RPC:
                plen = struct.unpack("<Q", await reader.readexactly(8))[0]
                payload = json.loads(await reader.readexactly(plen))
                resp = json.dumps({"echo": payload}).encode()
                writer.write(struct.pack("<Q", len(resp)))
                writer.write(resp)
                await writer.drain()

    except asyncio.IncompleteReadError:
        pass
    finally:
        writer.close()


def _sock_path():
    f = tempfile.NamedTemporaryFile(suffix=".sock", delete=False)
    path = f.name
    f.close()
    os.unlink(path)
    return path


# ── empty file ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_empty_file():
    _STORED.clear()
    path = _sock_path()
    srv = await asyncio.start_unix_server(_stateful_server, path=path)
    async with srv:
        async with VsockClient(path) as c:
            await c.send_file("empty.bin", b"")
            # Ping acts as a barrier: the server cannot reply to the ping
            # until it has finished processing the preceding SEND_FILE.
            await c.ping()
        assert _STORED.get("empty.bin") == b""


@pytest.mark.asyncio
async def test_fetch_nonexistent_returns_empty():
    _STORED.clear()
    path = _sock_path()
    srv = await asyncio.start_unix_server(_stateful_server, path=path)
    async with srv:
        async with VsockClient(path) as c:
            data = await c.fetch_file("no_such_file.txt")
    assert data == b""


# ── large payload ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_and_fetch_large_file():
    _STORED.clear()
    large = b"X" * (2 * 1024 * 1024)  # 2 MiB
    path = _sock_path()
    srv = await asyncio.start_unix_server(_stateful_server, path=path)
    async with srv:
        async with VsockClient(path) as c:
            await c.send_file("big.bin", large)
            received = await c.fetch_file("big.bin")
    assert received == large


@pytest.mark.asyncio
async def test_rpc_large_payload():
    _STORED.clear()
    path = _sock_path()
    srv = await asyncio.start_unix_server(_stateful_server, path=path)
    async with srv:
        async with VsockClient(path) as c:
            big_payload = {"data": "A" * 100_000}
            resp = await c.rpc(big_payload)
    assert resp["echo"]["data"] == "A" * 100_000


# ── multiple sequential operations ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_multiple_pings_in_one_connection():
    path = _sock_path()
    srv = await asyncio.start_unix_server(_stateful_server, path=path)
    async with srv:
        async with VsockClient(path) as c:
            for _ in range(5):
                assert await c.ping() is True


@pytest.mark.asyncio
async def test_send_then_rpc_same_connection():
    _STORED.clear()
    path = _sock_path()
    srv = await asyncio.start_unix_server(_stateful_server, path=path)
    async with srv:
        async with VsockClient(path) as c:
            await c.send_file("cfg.json", b'{"ok": true}')
            resp = await c.rpc({"action": "run"})
    assert resp["echo"]["action"] == "run"
    assert _STORED["cfg.json"] == b'{"ok": true}'


# ── connection refused ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connect_to_missing_socket_raises():
    with pytest.raises(Exception):
        async with VsockClient("/tmp/does_not_exist_abc123.sock") as c:
            await c.ping()


# ── wait_for_guest_ready ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_wait_for_guest_ready_succeeds():
    path = _sock_path()
    srv = await asyncio.start_unix_server(_stateful_server, path=path)
    async with srv:
        # Should succeed on first try since server is up
        await wait_for_guest_ready(path, retries=5, delay=0.05)


@pytest.mark.asyncio
async def test_wait_for_guest_ready_times_out():
    path = "/tmp/nc_test_no_server_xyz.sock"
    with pytest.raises(TimeoutError):
        await wait_for_guest_ready(path, retries=3, delay=0.01)


@pytest.mark.asyncio
async def test_wait_for_guest_ready_delayed_start():
    """Server starts after a delay — wait_for_guest_ready must retry."""
    path = _sock_path()

    async def start_server_late():
        await asyncio.sleep(0.1)
        srv = await asyncio.start_unix_server(_stateful_server, path=path)
        return srv

    srv_task = asyncio.create_task(start_server_late())
    await wait_for_guest_ready(path, retries=20, delay=0.05)
    srv = await srv_task
    srv.close()
