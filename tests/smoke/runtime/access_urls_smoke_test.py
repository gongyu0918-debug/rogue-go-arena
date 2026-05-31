from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import socket

from app.runtime.access_urls import get_access_urls, is_loopback_host


def fake_getaddrinfo(_host, _port, _family):
    return [
        (socket.AF_INET, None, None, None, ("127.0.0.1", 0)),
        (socket.AF_INET, None, None, None, ("192.168.1.20", 0)),
        (socket.AF_INET, None, None, None, ("10.0.0.8", 0)),
    ]


def failing_outbound_probe() -> str:
    raise OSError("simulated network probe failure")


def main() -> int:
    for host in ("127.0.0.1", "localhost", "::1"):
        assert is_loopback_host(host)
        urls = get_access_urls(host, 8000)
        assert urls == {
            "local": ["http://localhost:8000", "http://127.0.0.1:8000"],
            "lan": [],
        }

    wildcard_urls = get_access_urls(
        "0.0.0.0",
        8123,
        hostname_fn=lambda: "arena-host",
        getaddrinfo_fn=fake_getaddrinfo,
        outbound_ipv4_fn=lambda: "172.16.0.3",
    )
    assert wildcard_urls["local"] == [
        "http://localhost:8123",
        "http://127.0.0.1:8123",
    ]
    assert wildcard_urls["lan"] == [
        "http://10.0.0.8:8123",
        "http://172.16.0.3:8123",
        "http://192.168.1.20:8123",
    ]

    explicit_urls = get_access_urls(
        "192.168.50.9",
        9000,
        hostname_fn=lambda: "arena-host",
        getaddrinfo_fn=lambda *_args: [],
        outbound_ipv4_fn=lambda: None,
    )
    assert explicit_urls["lan"] == ["http://192.168.50.9:9000"]

    probe_failure_urls = get_access_urls(
        "0.0.0.0",
        8124,
        hostname_fn=lambda: "arena-host",
        getaddrinfo_fn=fake_getaddrinfo,
        outbound_ipv4_fn=failing_outbound_probe,
    )
    assert probe_failure_urls["lan"] == [
        "http://10.0.0.8:8124",
        "http://192.168.1.20:8124",
    ]

    print("access urls smoke test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
