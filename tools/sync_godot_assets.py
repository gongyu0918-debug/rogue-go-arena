from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_ASSETS = ROOT / "static" / "assets"
GODOT_ASSETS = ROOT / "client-godot" / "assets"

TEXTURES = (
    "board-kaya-classic-v1.png",
    "stone-black-traditional-v1.png",
    "stone-materials-tech-v3.png",
    "ui-dark-wood-v1.png",
    "board-table-scene-v4.png",
    "board-table-platform-v1.png",
)

ICON_DIRS = (
    ("icons/cards-tech", "*.png"),
    ("icons/toolbar-tech", "*.png"),
)


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def main() -> None:
    for name in TEXTURES:
        copy_file(
            STATIC_ASSETS / "textures" / name,
            GODOT_ASSETS / "textures" / name,
        )
    for rel_dir, pattern in ICON_DIRS:
        source_dir = STATIC_ASSETS / rel_dir
        target_dir = GODOT_ASSETS / rel_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        for source in source_dir.glob(pattern):
            copy_file(source, target_dir / source.name)
    total = sum(path.stat().st_size for path in GODOT_ASSETS.rglob("*") if path.is_file())
    count = sum(1 for path in GODOT_ASSETS.rglob("*") if path.is_file())
    print({"ok": True, "files": count, "bytes": total})


if __name__ == "__main__":
    main()
