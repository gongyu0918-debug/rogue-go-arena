from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import subprocess
import sys


def run_python(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", *args],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def smoke_remote_host_requires_explicit_opt_in() -> None:
    result = run_python(["server.py", "--no-katago", "--host", "0.0.0.0", "--port", "0"])

    assert result.returncode == 2
    assert "Refusing to bind to a non-loopback host" in result.stderr


def smoke_loopback_host_imports_normally() -> None:
    result = run_python(
        [
            "-c",
            (
                "import sys; "
                "sys.argv=['server.py','--no-katago','--host','127.0.0.1']; "
                "import server; "
                "print(server.SERVER_HOST)"
            ),
        ]
    )

    assert result.returncode == 0, result.stderr
    assert "127.0.0.1" in result.stdout


def smoke_remote_host_allows_explicit_opt_in() -> None:
    result = run_python(
        [
            "-c",
            (
                "import sys; "
                "sys.argv=['server.py','--no-katago','--host','0.0.0.0','--allow-remote']; "
                "import server; "
                "print(server.SERVER_HOST)"
            ),
        ]
    )

    assert result.returncode == 0, result.stderr
    assert "0.0.0.0" in result.stdout


def main() -> None:
    smoke_remote_host_requires_explicit_opt_in()
    smoke_loopback_host_imports_normally()
    smoke_remote_host_allows_explicit_opt_in()
    print("server host guard smoke test: OK")


if __name__ == "__main__":
    main()
