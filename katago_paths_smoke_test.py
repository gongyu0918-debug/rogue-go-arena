from __future__ import annotations

import tempfile
from pathlib import Path

import server as s
from app.runtime.katago_paths import (
    UserKataGoPaths,
    ensure_user_katago_dirs,
    write_runtime_katago_config,
)


def make_user_paths(root: Path) -> UserKataGoPaths:
    return UserKataGoPaths(
        data_dir=root / "data",
        katago_dir=root / "data" / "katago",
        home_dir=root / "data" / "katago" / "KataGoData",
        runtime_config_dir=root / "data" / "katago" / "runtime",
    )


def smoke_ensure_user_katago_dirs_creates_runtime_tree() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        paths = make_user_paths(Path(temp_dir))

        ensure_user_katago_dirs(paths)

        assert paths.data_dir.is_dir()
        assert paths.katago_dir.is_dir()
        assert paths.home_dir.is_dir()
        assert paths.runtime_config_dir.is_dir()


def smoke_runtime_config_rewrites_existing_home_data_dir() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        paths = make_user_paths(root)
        source_config = root / "katago.cfg"
        source_config.write_text(
            "numSearchThreads = 2\n# homeDataDir = old/path\nlogDir = logs\n",
            encoding="utf-8",
        )

        runtime_path = write_runtime_katago_config(source_config, paths)
        content = runtime_path.read_text(encoding="utf-8")

        assert runtime_path == paths.runtime_config_dir / "katago_runtime.cfg"
        assert f"homeDataDir = {paths.home_dir.as_posix()}" in content
        assert "old/path" not in content
        assert content.count("homeDataDir") == 1
        assert "numSearchThreads = 2" in content
        assert "logDir = logs" in content


def smoke_runtime_config_appends_missing_home_data_dir() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        paths = make_user_paths(root)
        source_config = root / "config_cpu.cfg"
        source_config.write_text("numSearchThreads = 1\n\n", encoding="utf-8")

        runtime_path = write_runtime_katago_config(source_config, paths)
        content = runtime_path.read_text(encoding="utf-8")

        assert runtime_path == paths.runtime_config_dir / "config_cpu_runtime.cfg"
        assert content == (
            "numSearchThreads = 1"
            f"\n\nhomeDataDir = {paths.home_dir.as_posix()}\n"
        )


def smoke_server_wrappers_use_current_user_paths() -> None:
    original_paths = s.USER_KATAGO_PATHS
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = make_user_paths(root)
            source_config = root / "server.cfg"
            source_config.write_text("homeDataDir = stale\n", encoding="utf-8")
            s.USER_KATAGO_PATHS = paths

            s._ensure_user_katago_dirs()
            runtime_path = s._runtime_config_path(source_config)
            content = runtime_path.read_text(encoding="utf-8")

            assert paths.home_dir.is_dir()
            assert runtime_path == paths.runtime_config_dir / "server_runtime.cfg"
            assert content == f"homeDataDir = {paths.home_dir.as_posix()}\n"
    finally:
        s.USER_KATAGO_PATHS = original_paths


def main() -> None:
    smoke_ensure_user_katago_dirs_creates_runtime_tree()
    smoke_runtime_config_rewrites_existing_home_data_dir()
    smoke_runtime_config_appends_missing_home_data_dir()
    smoke_server_wrappers_use_current_user_paths()
    print("katago paths smoke test: OK")


if __name__ == "__main__":
    main()
