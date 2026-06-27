from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import argparse
import json
import shutil
import subprocess

from tests.smoke._managed_source_server import ManagedSourceServer, ROOT, port_is_open


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Click the legacy desktop exit button in a real browser against a managed source server."
    )
    parser.add_argument("--port", type=int, default=0, help="Use 0 for a free port.")
    parser.add_argument("--startup-timeout", type=float, default=30.0)
    parser.add_argument("--smoke-timeout", type=float, default=120.0)
    parser.add_argument("--simulate-pywebview-close", action="store_true")
    args = parser.parse_args()

    with ManagedSourceServer(
        port=args.port,
        no_katago=True,
        artifact_subdir="legacy-desktop-exit-click-source-smoke",
        startup_timeout=args.startup_timeout,
    ) as server:
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        if not npm:
            raise RuntimeError("npm was not found on PATH")
        smoke_args = [
            npm,
            "run",
            "smoke:legacy-desktop-exit-click",
            "--prefix",
            "frontend",
            "--",
            f"--url={server.base_url}/",
        ]
        if args.simulate_pywebview_close:
            smoke_args.append("--simulate-pywebview-close")
        result = subprocess.run(
            smoke_args,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=args.smoke_timeout,
            check=False,
        )
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip())
        if result.returncode != 0:
            return result.returncode
        if server.process is None:
            raise RuntimeError("managed source server process missing")
        server.process.wait(timeout=10)
        returncode = server.process.returncode
        port_closed = not port_is_open(server.port)

    assert returncode == 0
    assert port_closed
    print(
        json.dumps(
            {
                "status": "passed",
                "port": server.port,
                "returncode": returncode,
                "port_closed": port_closed,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
