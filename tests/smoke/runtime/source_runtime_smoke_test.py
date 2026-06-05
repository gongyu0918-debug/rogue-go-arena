from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import argparse
import asyncio
import importlib.util
import json
from pathlib import Path
from typing import Any

from tests.smoke._managed_source_server import ManagedSourceServer


DEFAULT_PORT = 8877


def _load_runtime_smoke():
    smoke_path = Path(__file__).resolve().with_name("runtime_smoke_test.py")
    spec = importlib.util.spec_from_file_location("_rogue_go_runtime_smoke", smoke_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load runtime smoke from {smoke_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_smoke


run_smoke = _load_runtime_smoke()


async def run_managed_smoke(
    *,
    port: int,
    startup_timeout: float,
    runtime_timeout: float,
    no_katago: bool,
    status_only: bool,
    output: str,
) -> dict[str, Any]:
    server = ManagedSourceServer(
        port=port,
        no_katago=no_katago,
        artifact_subdir="source-runtime-smoke",
        startup_timeout=startup_timeout,
    )
    with server:
        startup_status = server.wait_for_status()
        if status_only:
            results = {
                "status": "passed",
                "source_status": startup_status,
                "managed_source": {
                    "port": server.port,
                    "pid": server.pid,
                    "log": str(server.log_path),
                },
            }
            if output:
                with open(output, "w", encoding="utf-8") as fh:
                    json.dump(results, fh, ensure_ascii=False, indent=2)
            return results
        results = await asyncio.wait_for(run_smoke(server.base_url), timeout=runtime_timeout)
        results["managed_source"] = {
            "port": server.port,
            "pid": server.pid,
            "startup_status": {
                "server_rev": startup_status.get("server_rev"),
                "no_katago": startup_status.get("no_katago"),
                "engine_phase": startup_status.get("engine_phase"),
                "engine_message": startup_status.get("engine_message"),
            },
            "log": str(server.log_path),
        }
        if output:
            with open(output, "w", encoding="utf-8") as fh:
                json.dump(results, fh, ensure_ascii=False, indent=2)
        return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Start a managed source server and run real runtime smoke tests."
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Use 0 for a free port.")
    parser.add_argument("--startup-timeout", type=float, default=60.0)
    parser.add_argument("--runtime-timeout", type=float, default=300.0)
    parser.add_argument("--no-katago", action="store_true")
    parser.add_argument("--status-only", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    results = asyncio.run(
        run_managed_smoke(
            port=args.port,
            startup_timeout=args.startup_timeout,
            runtime_timeout=args.runtime_timeout,
            no_katago=args.no_katago,
            status_only=args.status_only,
            output=args.output,
        )
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if args.status_only:
        return 0 if results.get("status") == "passed" else 1
    failures = [
        key
        for key in ("normal", "rogue", "ultimate", "observer", "capture_rule", "ko_rule")
        if results.get(key, {}).get("status") != "passed"
    ]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
