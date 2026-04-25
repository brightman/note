"""Integration test: VsockClient ↔ a local echo server (no actual VM)."""

import asyncio
import json
import struct
import tempfile
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "control-plane"))

import pytest

CMD_SEND_FILE = 0x01
CMD_FETCH_FILE = 0x02
CMD_RPC = 0x03
CMD_PING = 0xFF


async def _echo_server(reader, writer):
    """Minimal server that implements the vsock protocol."""
    try:
        while True:
            cmd_b = await reader.readexactly(4)
            cmd = struct.unpack("<I", cmd_b)[0]

            if cmd == CMD_PING:
                writer.write(struct.pack("<I", CMD_PING))
                await writer.drain()

            elif cmd == CMD_SEND_FILE:
                nlen = struct.unpack("<I", await reader.readexactly(4))[0]
                await reader.readexactly(nlen)
                dlen = struct.unpack("<Q", await reader.readexactly(8))[0]
                await reader.readexactly(dlen)

            elif cmd == CMD_FETCH_FILE:
                nlen = struct.unpack("<I", await reader.readexactly(4))[0]
                await reader.readexactly(nlen)
                data = b"hello from guest"
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


@pytest.mark.asyncio
async def test_ping():
    with tempfile.NamedTemporaryFile(suffix=".sock", delete=False) as f:
        sock_path = f.name
    os.unlink(sock_path)

    srv = await asyncio.start_unix_server(_echo_server, path=sock_path)
    async with srv:
        from vm.vsock_client import VsockClient
        async with VsockClient(sock_path) as c:
            assert await c.ping() is True


@pytest.mark.asyncio
async def test_send_and_fetch_file():
    with tempfile.NamedTemporaryFile(suffix=".sock", delete=False) as f:
        sock_path = f.name
    os.unlink(sock_path)

    srv = await asyncio.start_unix_server(_echo_server, path=sock_path)
    async with srv:
        from vm.vsock_client import VsockClient
        async with VsockClient(sock_path) as c:
            await c.send_file("config.json", b'{"test": true}')
            data = await c.fetch_file("config.json")
            assert data == b"hello from guest"


@pytest.mark.asyncio
async def test_rpc():
    with tempfile.NamedTemporaryFile(suffix=".sock", delete=False) as f:
        sock_path = f.name
    os.unlink(sock_path)

    srv = await asyncio.start_unix_server(_echo_server, path=sock_path)
    async with srv:
        from vm.vsock_client import VsockClient
        async with VsockClient(sock_path) as c:
            resp = await c.rpc({"message": "hello"})
            assert resp["echo"]["message"] == "hello"
