"""ローカルネットワーク情報の取得ユーティリティ。"""

from __future__ import annotations

import ipaddress
import re
import socket
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class NetworkInterface:
    name: str
    address: str


def get_local_ipv4_addresses() -> list[str]:
    """LAN内から到達しやすいIPv4アドレス候補を返す。"""
    interfaces = get_local_ipv4_interfaces()
    if interfaces:
        return [interface.address for interface in interfaces]

    return _fallback_local_ipv4_addresses()


def get_local_ipv4_interfaces() -> list[NetworkInterface]:
    if sys.platform.startswith("win"):
        interfaces = _windows_ipconfig_interfaces()
        if interfaces:
            return interfaces

    return [
        NetworkInterface(name=address, address=address)
        for address in _fallback_local_ipv4_addresses()
    ]


def get_mobile_score_url(port: int, interface_name: str = "") -> str | None:
    interfaces = get_local_ipv4_interfaces()
    if not interfaces:
        return None

    if interface_name:
        for interface in interfaces:
            if interface.name == interface_name:
                return f"http://{interface.address}:{int(port)}/"
        return None

    return f"http://{interfaces[0].address}:{int(port)}/"


def get_mobile_score_urls(port: int) -> list[str]:
    return [f"http://{address}:{int(port)}/" for address in get_local_ipv4_addresses()]


def _fallback_local_ipv4_addresses() -> list[str]:
    addresses: list[str] = []

    def add_address(address: str) -> None:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return
        if ip.version != 4 or ip.is_loopback or ip.is_link_local:
            return
        if address not in addresses:
            addresses.append(address)

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            add_address(info[4][0])
    except OSError:
        pass

    if addresses:
        return sorted(addresses, key=_address_sort_key)

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            add_address(sock.getsockname()[0])
    except OSError:
        pass

    return sorted(addresses, key=_address_sort_key)


def _windows_ipconfig_interfaces() -> list[NetworkInterface]:
    try:
        result = subprocess.run(
            ["ipconfig"],
            capture_output=True,
            text=True,
            encoding="mbcs",
            errors="replace",
            timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return []

    interfaces: list[NetworkInterface] = []
    current_name = ""
    for raw_line in result.stdout.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue

        if not raw_line.startswith((" ", "\t")) and line.endswith(":"):
            current_name = line[:-1].strip()
            continue

        match = re.search(r"IPv4[^:]*:\s*([0-9]+(?:\.[0-9]+){3})", line)
        if not match or not current_name:
            continue

        address = match.group(1)
        if _is_usable_ipv4(address) and not any(
            item.name == current_name and item.address == address for item in interfaces
        ):
            interfaces.append(NetworkInterface(current_name, address))

    return sorted(interfaces, key=lambda item: (_address_sort_key(item.address), item.name))


def _is_usable_ipv4(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return ip.version == 4 and not ip.is_loopback and not ip.is_link_local


def _address_sort_key(address: str) -> tuple[int, str]:
    ip = ipaddress.ip_address(address)
    return (0 if ip.is_private else 1, address)
