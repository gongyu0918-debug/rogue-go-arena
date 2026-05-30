from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class UserKataGoPaths:
    data_dir: Path
    katago_dir: Path
    home_dir: Path
    runtime_config_dir: Path


def ensure_user_katago_dirs(paths: UserKataGoPaths) -> None:
    for path in (
        paths.data_dir,
        paths.katago_dir,
        paths.home_dir,
        paths.runtime_config_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)


def write_runtime_katago_config(source_config: Path, paths: UserKataGoPaths) -> Path:
    ensure_user_katago_dirs(paths)
    runtime_path = paths.runtime_config_dir / f"{source_config.stem}_runtime.cfg"
    content = source_config.read_text(encoding="utf-8", errors="ignore")
    home_dir = paths.home_dir.as_posix()

    if re.search(r"(?m)^\s*#?\s*homeDataDir\s*=", content):
        content = re.sub(
            r"(?m)^\s*#?\s*homeDataDir\s*=.*$",
            f"homeDataDir = {home_dir}",
            content,
            count=1,
        )
    else:
        content = content.rstrip() + f"\n\nhomeDataDir = {home_dir}\n"

    runtime_path.write_text(content, encoding="utf-8")
    return runtime_path
