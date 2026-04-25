#!/usr/bin/env python3
"""
Guest-side vsock receiver.

Runs inside the Firecracker VM. Listens on vsock port 1024 (exposed as a
Unix socket by Firecracker to the host). Receives injected files and
forwards RPC messages to the local nanobot process.

Protocol: same as vm/vsock_client.py
"""

import asyncio
import json
import logging
import os
import struct
import sys
import tarfile
import io
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("vsock-receiver")

NANOBOT_HOME = Path(os.environ.get("NANOBOT_HOME", "/home/nanobot/.nanobot"))
VSOCK_PORT = int(os.environ.get("VSOCK_PORT", "1024"))
NANOBOT_WS_URL = os.environ.get("NANOBOT_WS_URL", "http://127.0.0.1:8765")

CMD_SEND_FILE = 0x01
CMD_FETCH_FILE = 0x02
CMD_RPC = 0x03
CMD_PING = 0xFF


class ReceiverServer:
    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername", "unknown")
        log.info("connection from %s", peer)
        try:
            while True:
                cmd_data = await reader.readexactly(4)
                cmd = struct.unpack("<I", cmd_data)[0]
                if cmd == CMD_PING:
                    writer.write(struct.pack("<I", CMD_PING))
                    await writer.drain()
                elif cmd == CMD_SEND_FILE:
                    await self._recv_file(reader)
                elif cmd == CMD_FETCH_FILE:
                    await self._send_file(reader, writer)
                elif cmd == CMD_RPC:
                    await self._handle_rpc(reader, writer)
                else:
                    log.warning("unknown cmd 0x%02x", cmd)
                    break
        except asyncio.IncompleteReadError:
            pass
        except Exception as e:
            log.exception("handler error: %s", e)
        finally:
            writer.close()

    async def _recv_file(self, reader: asyncio.StreamReader) -> None:
        name_len = struct.unpack("<I", await reader.readexactly(4))[0]
        name = (await reader.readexactly(name_len)).decode()
        data_len = struct.unpack("<Q", await reader.readexactly(8))[0]
        data = await reader.readexactly(data_len)

        dest = NANOBOT_HOME / name
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Special handling: memory archive
        if name == "memory.tar.gz":
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
                tf.extractall(NANOBOT_HOME)
            log.info("restored memory from archive (%d bytes)", data_len)
        # Special handling: skills directory bundle
        elif name == "skills.tar.gz":
            skills_dir = NANOBOT_HOME / "skills"
            skills_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
                tf.extractall(skills_dir)
            log.info("restored skills from archive (%d bytes)", data_len)
        else:
            dest.write_bytes(data)
            log.info("received file %s (%d bytes)", name, data_len)

    async def _send_file(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        name_len = struct.unpack("<I", await reader.readexactly(4))[0]
        name = (await reader.readexactly(name_len)).decode()

        # Special handling: pack memory directory as tar.gz
        if name == "memory.tar.gz":
            memory_dir = NANOBOT_HOME / "memory"
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w:gz") as tf:
                if memory_dir.exists():
                    tf.add(memory_dir, arcname="memory")
            data = buf.getvalue()
        else:
            path = NANOBOT_HOME / name
            data = path.read_bytes() if path.exists() else b""

        writer.write(struct.pack("<Q", len(data)))
        writer.write(data)
        await writer.drain()
        log.info("sent file %s (%d bytes)", name, len(data))

    async def _handle_rpc(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        payload_len = struct.unpack("<Q", await reader.readexactly(8))[0]
        payload = json.loads(await reader.readexactly(payload_len))

        response = await self._forward_to_nanobot(payload)

        resp_data = json.dumps(response).encode()
        writer.write(struct.pack("<Q", len(resp_data)))
        writer.write(resp_data)
        await writer.drain()

    async def _forward_to_nanobot(self, payload: dict) -> dict:
        """Forward an RPC message to the local nanobot gateway via HTTP."""
        import urllib.request
        import urllib.error

        url = f"{NANOBOT_WS_URL}/v1/chat/completions"
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read())
        except urllib.error.URLError as e:
            return {"error": str(e)}


async def main() -> None:
    NANOBOT_HOME.mkdir(parents=True, exist_ok=True)

    # Firecracker exposes vsock as a Unix socket at a well-known path
    sock_path = f"/tmp/vsock-{VSOCK_PORT}.sock"
    if Path(sock_path).exists():
        Path(sock_path).unlink()

    server = ReceiverServer()
    srv = await asyncio.start_unix_server(server.handle, path=sock_path)
    log.info("vsock receiver listening on %s", sock_path)

    async with srv:
        await srv.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
