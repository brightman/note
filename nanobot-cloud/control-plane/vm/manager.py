"""
Firecracker VM lifecycle manager.

Each user gets at most one running VM at a time.
VMs are started on demand and stopped after IDLE_TIMEOUT seconds of inactivity.
Memory is persisted to S3 on shutdown and restored on the next start.
"""

import asyncio
import io
import json
import logging
import os
import tarfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from config.injector import build_nanobot_config, config_to_bytes, load_skills
from settings import settings
from storage import s3 as s3_store
from vm.network import allocate_ip, create_tap, delete_tap, mac_for_vm
from vm.vsock_client import VsockClient, wait_for_guest_ready

log = logging.getLogger(__name__)


@dataclass
class VMState:
    user_id: uuid.UUID
    vm_id: str
    api_sock: str        # Firecracker management API socket
    vsock_path: str      # Host-side Unix socket that fronts vsock
    guest_ip: str
    tap_name: str
    process: asyncio.subprocess.Process
    last_active: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    task_count: int = 0


class FirecrackerVMManager:
    def __init__(self, db_session_factory, *, loop: asyncio.AbstractEventLoop | None = None):
        self._session_factory = db_session_factory
        self._vms: dict[uuid.UUID, VMState] = {}
        self._lock = asyncio.Lock()

    # ── public API ──────────────────────────────────────────────────────────

    async def get_or_create(self, user_id: uuid.UUID) -> VMState:
        async with self._lock:
            if user_id in self._vms:
                vm = self._vms[user_id]
                vm.last_active = datetime.now(timezone.utc)
                return vm
            return await self._start_vm(user_id)

    async def stop(self, user_id: uuid.UUID, *, persist: bool = True) -> None:
        async with self._lock:
            vm = self._vms.pop(user_id, None)
        if vm is None:
            return
        await self._stop_vm(vm, persist=persist)

    async def rpc(self, user_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any]:
        vm = await self.get_or_create(user_id)
        vm.task_count += 1
        vm.last_active = datetime.now(timezone.utc)
        try:
            async with VsockClient(vm.vsock_path) as client:
                return await client.rpc(payload)
        finally:
            vm.task_count -= 1
            vm.last_active = datetime.now(timezone.utc)

    @property
    def active_vms(self) -> dict[uuid.UUID, VMState]:
        return dict(self._vms)

    # ── VM start ────────────────────────────────────────────────────────────

    async def _start_vm(self, user_id: uuid.UUID) -> VMState:
        vm_id = f"nb{str(user_id).replace('-', '')[:12]}"
        api_sock = f"{settings.fc_api_sock_dir}/{vm_id}.sock"
        vsock_path = f"{settings.fc_vsock_dir}/{vm_id}.sock"
        Path(settings.fc_api_sock_dir).mkdir(parents=True, exist_ok=True)
        Path(settings.fc_vsock_dir).mkdir(parents=True, exist_ok=True)

        guest_ip = allocate_ip(vm_id)
        tap_name = await create_tap(vm_id)

        log.info("starting VM %s for user %s (ip=%s)", vm_id, user_id, guest_ip)

        proc = await self._launch_firecracker(vm_id, api_sock, vsock_path, tap_name, guest_ip)

        # Wait for Firecracker API to be ready
        await self._wait_fc_api(api_sock)

        # Build guest config from DB
        async with self._session_factory() as session:
            nanobot_cfg = await build_nanobot_config(user_id, session)
            skills = await load_skills(user_id, session)

        # Wait for guest vsock receiver to accept connections
        await wait_for_guest_ready(vsock_path)

        # Inject config + skills + memory
        await self._inject_guest(vsock_path, nanobot_cfg, skills, user_id)

        vm = VMState(
            user_id=user_id,
            vm_id=vm_id,
            api_sock=api_sock,
            vsock_path=vsock_path,
            guest_ip=guest_ip,
            tap_name=tap_name,
            process=proc,
        )
        self._vms[user_id] = vm
        log.info("VM %s ready", vm_id)
        return vm

    async def _launch_firecracker(
        self,
        vm_id: str,
        api_sock: str,
        vsock_path: str,
        tap_name: str,
        guest_ip: str,
    ) -> asyncio.subprocess.Process:
        fc_config = {
            "boot-source": {
                "kernel_image_path": settings.fc_kernel,
                "boot_args": (
                    f"console=ttyS0 reboot=k panic=1 pci=off "
                    f"ip={guest_ip}::{ settings.host_gateway_ip}:255.255.0.0::eth0:off"
                ),
            },
            "drives": [
                {
                    "drive_id": "rootfs",
                    "path_on_host": settings.fc_rootfs,
                    "is_root_device": True,
                    "is_read_only": True,
                }
            ],
            "machine-config": {
                "vcpu_count": settings.vm_vcpu,
                "mem_size_mib": settings.vm_mem_mib,
            },
            "vsock": {
                "guest_cid": 3,
                "uds_path": vsock_path,
            },
            "network-interfaces": [
                {
                    "iface_id": "eth0",
                    "guest_mac": mac_for_vm(vm_id),
                    "host_dev_name": tap_name,
                }
            ],
        }

        cfg_path = f"/tmp/fc-cfg-{vm_id}.json"
        Path(cfg_path).write_text(json.dumps(fc_config))

        proc = await asyncio.create_subprocess_exec(
            settings.fc_binary,
            "--api-sock", api_sock,
            "--config-file", cfg_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        return proc

    async def _wait_fc_api(self, api_sock: str, retries: int = 30, delay: float = 0.3) -> None:
        transport = httpx.AsyncHTTPTransport(uds=api_sock)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            for _ in range(retries):
                try:
                    r = await client.get("/")
                    if r.status_code < 500:
                        return
                except Exception:
                    pass
                await asyncio.sleep(delay)
        raise TimeoutError(f"Firecracker API at {api_sock} never became ready")

    async def _inject_guest(
        self,
        vsock_path: str,
        nanobot_cfg: dict,
        skills: list[dict],
        user_id: uuid.UUID,
    ) -> None:
        async with VsockClient(vsock_path) as client:
            # config.json
            await client.send_file("config.json", config_to_bytes(nanobot_cfg))

            # skills as a tar archive
            if skills:
                buf = io.BytesIO()
                with tarfile.open(fileobj=buf, mode="w:gz") as tf:
                    for skill in skills:
                        ext = ".py" if skill["skill_type"] == "python" else ".md"
                        fname = f"{skill['name']}{ext}"
                        data = skill["content"].encode()
                        info = tarfile.TarInfo(name=fname)
                        info.size = len(data)
                        tf.addfile(info, io.BytesIO(data))
                await client.send_file("skills.tar.gz", buf.getvalue())

            # memory from S3 (if exists)
            memory_data = await s3_store.get_object(f"memory/{user_id}.tar.gz")
            if memory_data:
                await client.send_file("memory.tar.gz", memory_data)

    # ── VM stop ─────────────────────────────────────────────────────────────

    async def _stop_vm(self, vm: VMState, *, persist: bool = True) -> None:
        log.info("stopping VM %s (persist=%s)", vm.vm_id, persist)

        if persist:
            try:
                async with VsockClient(vm.vsock_path) as client:
                    memory_data = await client.fetch_file("memory.tar.gz")
                if memory_data:
                    await s3_store.put_object(f"memory/{vm.user_id}.tar.gz", memory_data)
            except Exception as e:
                log.warning("could not persist memory for %s: %s", vm.vm_id, e)

        # Send ACPI shutdown via Firecracker API
        try:
            transport = httpx.AsyncHTTPTransport(uds=vm.api_sock)
            async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
                await client.put("/actions", json={"action_type": "SendCtrlAltDel"})
        except Exception:
            pass

        # Give it a moment, then force-kill
        try:
            await asyncio.wait_for(vm.process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            vm.process.kill()
            await vm.process.wait()

        await delete_tap(vm.vm_id)

        # Clean up temp files
        for path in (vm.api_sock, vm.vsock_path, f"/tmp/fc-cfg-{vm.vm_id}.json"):
            try:
                Path(path).unlink(missing_ok=True)
            except Exception:
                pass

        log.info("VM %s stopped", vm.vm_id)


# Module-level singleton, initialised in app lifespan
_manager: FirecrackerVMManager | None = None


def get_manager() -> FirecrackerVMManager:
    if _manager is None:
        raise RuntimeError("VM manager not initialised")
    return _manager


def init_manager(session_factory) -> FirecrackerVMManager:
    global _manager
    _manager = FirecrackerVMManager(session_factory)
    return _manager
