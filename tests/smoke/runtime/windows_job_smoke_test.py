from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import os
import subprocess
import sys

from app.runtime.windows_job import attach_kill_on_close_job, close_kill_on_close_job


def smoke_closing_job_terminates_child_process() -> None:
    if os.name != "nt":
        return

    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        assert attach_kill_on_close_job(process) is True
        close_kill_on_close_job(process)
        process.wait(timeout=5)
        assert process.poll() is not None
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def main() -> None:
    smoke_closing_job_terminates_child_process()
    print("windows job smoke test: OK")


if __name__ == "__main__":
    main()
