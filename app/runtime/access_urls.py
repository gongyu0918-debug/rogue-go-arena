from __future__ import annotations

import socket
from collections.abc import Callable
from typing import Any


def is_loopback_host(host: str) -> bool:
    host = (host or "").strip().lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def get_access_urls(
    host: str,
    port: int,
    *,
    hostname_fn: Callable[[], str] = socket.gethostname,
    getaddrinfo_fn: Callable[..., list[Any]] = socket.getaddrinfo,
    outbound_ipv4_fn: Callable[[], str | None] | None = None,
) -> dict[str, list[str]]:
    if is_loopback_host(host):
        return {
            "local": local_access_urls(port),
            "lan": [],
        }

    lan_ips = set()
    if host and host not in {"0.0.0.0", "::"} and not is_loopback_host(host):
        lan_ips.add(host)
    lan_ips.update(_hostname_ipv4_addresses(hostname_fn, getaddrinfo_fn))

    probe = outbound_ipv4_fn or _probe_outbound_ipv4
    try:
        outbound_ip = probe()
    except OSError:
        outbound_ip = None
    if outbound_ip and not outbound_ip.startswith("127."):
        lan_ips.add(outbound_ip)

    return {
        "local": local_access_urls(port),
        "lan": [f"http://{ip}:{port}" for ip in sorted(lan_ips)],
    }


def local_access_urls(port: int) -> list[str]:
    return [
        f"http://localhost:{port}",
        f"http://127.0.0.1:{port}",
    ]


def _hostname_ipv4_addresses(
    hostname_fn: Callable[[], str],
    getaddrinfo_fn: Callable[..., list[Any]],
) -> set[str]:
    ips: set[str] = set()
    try:
        for item in getaddrinfo_fn(hostname_fn(), None, socket.AF_INET):
            ip = item[4][0]
            if ip and not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    return ips


def _probe_outbound_ipv4() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return None
