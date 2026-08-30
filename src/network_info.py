"""ローカルネットワーク情報の取得ユーティリティ。"""

from __future__ import annotations

import ipaddress
import socket


def get_local_ipv4_addresses() -> list[str]:
    """LAN内から到達しやすいIPv4アドレス候補を返す。"""
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


def get_mobile_score_urls(port: int) -> list[str]:
    return [f"http://{address}:{int(port)}/" for address in get_local_ipv4_addresses()]


def _address_sort_key(address: str) -> tuple[int, str]:
    ip = ipaddress.ip_address(address)
    return (0 if ip.is_private else 1, address)
