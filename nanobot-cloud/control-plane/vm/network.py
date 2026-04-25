"""Manage tap devices and iptables rules for Firecracker VMs."""

import asyncio
import ipaddress
import logging
import re

from settings import settings

log = logging.getLogger(__name__)

_SUBNET = ipaddress.IPv4Network(settings.vm_subnet)
# Start allocating from .2 (host bridge takes .1)
_ALLOCATED: dict[str, str] = {}  # vm_id -> guest_ip


def allocate_ip(vm_id: str) -> str:
    if vm_id in _ALLOCATED:
        return _ALLOCATED[vm_id]
    used = set(_ALLOCATED.values())
    for host in _SUBNET.hosts():
        ip = str(host)
        if ip == settings.host_gateway_ip:
            continue
        if ip not in used:
            _ALLOCATED[vm_id] = ip
            return ip
    raise RuntimeError("IP pool exhausted")


def release_ip(vm_id: str) -> None:
    _ALLOCATED.pop(vm_id, None)


async def create_tap(vm_id: str) -> str:
    tap_name = f"{settings.fc_tap_prefix}-{vm_id[:8]}"
    await _run(f"ip tuntap add dev {tap_name} mode tap")
    await _run(f"ip link set dev {tap_name} up")
    await _run(
        f"iptables -t nat -A POSTROUTING -s {settings.vm_subnet} -o eth0 -j MASQUERADE"
    )
    await _run(f"iptables -A FORWARD -i {tap_name} -j ACCEPT")
    await _run(f"iptables -A FORWARD -o {tap_name} -j ACCEPT")
    log.info("created tap %s", tap_name)
    return tap_name


async def delete_tap(vm_id: str) -> None:
    tap_name = f"{settings.fc_tap_prefix}-{vm_id[:8]}"
    await _run(f"iptables -D FORWARD -i {tap_name} -j ACCEPT", check=False)
    await _run(f"iptables -D FORWARD -o {tap_name} -j ACCEPT", check=False)
    await _run(f"ip link del dev {tap_name}", check=False)
    release_ip(vm_id)
    log.info("deleted tap %s", tap_name)


def mac_for_vm(vm_id: str) -> str:
    # Deterministic MAC from vm_id prefix
    hex_id = vm_id.replace("-", "")[:10].ljust(10, "0")
    return f"AA:FC:{hex_id[0:2]}:{hex_id[2:4]}:{hex_id[4:6]}:{hex_id[6:8]}"


async def _run(cmd: str, check: bool = True) -> None:
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed: {cmd!r} → {stderr.decode().strip()}")
