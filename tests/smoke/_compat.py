from __future__ import annotations

from pathlib import Path
import runpy
import sys


ROOT = Path(__file__).resolve().parents[2]


def run_smoke(relative_path: str) -> None:
    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    script_path = ROOT / relative_path
    script_dir = str(script_path.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    original_argv = sys.argv[:]
    sys.argv = [str(script_path), *sys.argv[1:]]
    try:
        runpy.run_path(str(script_path), run_name="__main__")
    finally:
        sys.argv = original_argv
