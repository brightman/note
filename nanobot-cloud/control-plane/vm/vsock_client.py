"""
Host-side vsock client.

Protocol (all little-endian):
  SEND_FILE:  [4B cmd=0x01][4B name_len][name][8B data_len][data]
  FETCH_FILE: [4B cmd=0x02][4B name_len][name]  →  [8B data_len][data]
  RPC:        [4B cmd=0x03][8B payload_len][payload_json]  →  [8B resp_len][resp_json]
  PING:       [4B cmd=0xFF]  →  [4B pong=0xFF]
"""

import asyncio
import struct
from pathlib import Path
from typing import Any
import json

CMD_SEND_FILE = 0x01
CMD_FETCH_FILE = 0x02
CMD_RPC = 0x03
CMD_PING = 0xFF

CONNECT_TIMEOUT = 10.0
RPC_TIMEOUT = 120.0


class VsockClient:
    """Connect to a Firecracker guest via a Unix socket that fronts the vsock."""

    def __init__(self, uds_path: str):
        self._path = uds_path
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def __aenter__(self) -> "VsockClient":
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_unix_connection(self._path), timeout=CONNECT_TIMEOUT
        )
        return self

    async def __aexit__(self, *_) -> None:
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass

    # ── public API ──────────────────────────────────────────────────────────

    async def ping(self) -> bool:
        self._write_u32(CMD_PING)
        await self._writer.drain()
        pong = await self._read_u32()
        return pong == CMD_PING

    async def send_file(self, name: str, data: bytes) -> None:
        name_b = name.encode()
        self._write_u32(CMD_SEND_FILE)
        self._write_u32(len(name_b))
        self._writer.write(name_b)
        self._write_u64(len(data))
        self._writer.write(data)
        await self._writer.drain()

    async def fetch_file(self, name: str) -> bytes:
        name_b = name.encode()
        self._write_u32(CMD_FETCH_FILE)
        self._write_u32(len(name_b))
        self._writer.write(name_b)
        await self._writer.drain()
        length = await self._read_u64()
        return await self._reader.readexactly(length)

    async def rpc(self, payload: dict[str, Any], timeout: float = RPC_TIMEOUT) -> dict[str, Any]:
        data = json.dumps(payload).encode()
        self._write_u32(CMD_RPC)
        self._write_u64(len(data))
        self._writer.write(data)
        await self._writer.drain()
        resp_len = await asyncio.wait_for(self._read_u64(), timeout=timeout)
        resp_data = await asyncio.wait_for(self._reader.readexactly(resp_len), timeout=timeout)
        return json.loads(resp_data)

    # ── helpers ─────────────────────────────────────────────────────────────

    def _write_u32(self, v: int) -> None:
        self._writer.write(struct.pack("<I", v))

    def _write_u64(self, v: int) -> None:
        self._writer.write(struct.pack("<Q", v))

    async def _read_u32(self) -> int:
        data = await self._reader.readexactly(4)
        return struct.unpack("<I", data)[0]

    async def _read_u64(self) -> int:
        data = await self._reader.readexactly(8)
        return struct.unpack("<Q", data)[0]


async def wait_for_guest_ready(uds_path: str, retries: int = 20, delay: float = 0.5) -> None:
    """Poll until the guest vsock receiver accepts connections."""
    for attempt in range(retries):
        try:
            async with VsockClient(uds_path) as c:
                if await c.ping():
                    return
        except Exception:
            pass
        await asyncio.sleep(delay)
    raise TimeoutError(f"Guest at {uds_path} never became ready after {retries} attempts")
