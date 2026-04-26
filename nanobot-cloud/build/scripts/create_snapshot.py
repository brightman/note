#!/usr/bin/env python3
"""
Boot a template VM, wait for nanobot to initialise, then snapshot it.
The snapshot is used for sub-50ms cold starts.
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx

SNAP_DIR = "/opt/fc-snapshots"
API_SOCK = "/tmp/fc-snap-template.sock"
VSOCK_PATH = "/tmp/fc-snap-vsock.sock"


async def main() -> None:
    Path(SNAP_DIR).mkdir(parents=True, exist_ok=True)

    fc_config = {
        "boot-source": {
            "kernel_image_path": "/opt/fc-kernels/vmlinux",
            "boot_args": "console=ttyS0 reboot=k panic=1 pci=off",
        },
        "drives": [
            {
                "drive_id": "rootfs",
                "path_on_host": "/opt/fc-images/nanobot-rootfs.ext4",
                "is_root_device": True,
                "is_read_only": True,
            }
        ],
        "machine-config": {"vcpu_count": 1, "mem_size_mib": 256},
        "vsock": {"guest_cid": 3, "uds_path": VSOCK_PATH},
    }

    cfg_path = "/tmp/fc-snap-config.json"
    Path(cfg_path).write_text(json.dumps(fc_config))

    proc = await asyncio.create_subprocess_exec(
        "firecracker",
        "--api-sock", API_SOCK,
        "--config-file", cfg_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )

    print("Waiting for Firecracker API...")
    transport = httpx.AsyncHTTPTransport(uds=API_SOCK)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        for _ in range(60):
            try:
                r = await client.get("/")
                if r.status_code < 500:
                    break
            except Exception:
                pass
            await asyncio.sleep(0.5)

    # Pause VM before snapshot
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        await client.patch("/vm", json={"state": "Paused"})
        await client.put(
            "/snapshot/create",
            json={
                "snapshot_type": "Full",
                "snapshot_path": f"{SNAP_DIR}/nanobot-base.snap",
                "mem_file_path": f"{SNAP_DIR}/nanobot-base.mem",
            },
        )
        print(f"Snapshot saved to {SNAP_DIR}/")
        await client.put("/actions", json={"action_type": "SendCtrlAltDel"})

    await proc.wait()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
