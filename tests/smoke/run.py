from __future__ import annotations

import argparse
from pathlib import Path
import runpy
import sys


ROOT = Path(__file__).resolve().parents[2]
SMOKE_ROOT = Path(__file__).resolve().parent


def smoke_scripts() -> list[Path]:
    return sorted(
        path
        for path in SMOKE_ROOT.rglob("*.py")
        if path.name not in {"__init__.py", "run.py"}
        and not path.name.startswith("_")
    )


def resolve_script(selector: str) -> Path:
    candidate = Path(selector)
    if (candidate.is_absolute() or len(candidate.parts) > 1) and candidate.exists():
        return candidate.resolve()

    smoke_candidate = SMOKE_ROOT / selector
    if smoke_candidate.exists():
        return smoke_candidate.resolve()

    matches = [path for path in smoke_scripts() if path.name == selector]
    if not matches:
        raise SystemExit(f"Unknown smoke script: {selector}")
    if len(matches) > 1:
        options = ", ".join(str(path.relative_to(ROOT)) for path in matches)
        raise SystemExit(f"Ambiguous smoke script {selector}: {options}")
    return matches[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run categorized smoke scripts.")
    parser.add_argument("script", nargs="?", help="Smoke script filename or path.")
    parser.add_argument("script_args", nargs=argparse.REMAINDER)
    parser.add_argument("--list", action="store_true", help="List available smoke scripts.")
    args = parser.parse_args(argv)

    if args.list:
        for path in smoke_scripts():
            print(path.relative_to(ROOT).as_posix())
        return 0

    if not args.script:
        parser.error("script is required unless --list is used")

    script_path = resolve_script(args.script)
    for path in (ROOT, script_path.parent):
        path_text = str(path)
        if path_text not in sys.path:
            sys.path.insert(0, path_text)

    sys.argv = [str(script_path), *args.script_args]
    runpy.run_path(str(script_path), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
