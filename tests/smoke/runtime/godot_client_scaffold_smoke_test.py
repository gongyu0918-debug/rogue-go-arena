from __future__ import annotations

from pathlib import Path

from _path_bootstrap import ensure_repo_root


ensure_repo_root(__file__)
ROOT = Path(__file__).resolve().parents[3]
CLIENT = ROOT / "client-godot"


def main() -> None:
    required = [
        CLIENT / "project.godot",
        CLIENT / "RogueGoArena.csproj",
        CLIENT / "scenes" / "Main.tscn",
        CLIENT / "scripts" / "Main.cs",
        CLIENT / "scripts" / "BoardView.cs",
        CLIENT / "scripts" / "RuntimeWorker.cs",
        CLIENT / "scripts" / "StaticAssetTextureRect.cs",
        CLIENT / "scripts" / "CardIconTray.cs",
        CLIENT / "scripts" / "ToolbarStrip.cs",
        CLIENT / "assets" / "textures" / "board-kaya-classic-v1.png",
        CLIENT / "assets" / "textures" / "stone-black-traditional-v1.png",
        CLIENT / "assets" / "textures" / "stone-materials-tech-v3.png",
        CLIENT / "assets" / "textures" / "ui-dark-wood-v1.png",
        CLIENT / "assets" / "icons" / "cards-tech" / "blackhole.png",
        CLIENT / "assets" / "icons" / "toolbar-tech" / "settings.png",
    ]
    missing = [str(path) for path in required if not path.exists()]
    assert not missing, f"missing Godot client files: {missing}"

    project_text = (CLIENT / "project.godot").read_text(encoding="utf-8")
    assert 'run/main_scene="res://scenes/Main.tscn"' in project_text
    assert 'project/assembly_name="RogueGoArena"' in project_text

    text_files = [path for path in required if path.suffix.lower() in {".cs", ".tscn", ".godot", ".csproj"}]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in text_files)
    forbidden = ["WebSocket", "uvicorn", "FastAPI", "http://127.0.0.1", "localhost:8000"]
    found = [needle for needle in forbidden if needle in combined]
    assert not found, f"Godot client scaffold still references web runtime: {found}"

    worker_text = (CLIENT / "scripts" / "RuntimeWorker.cs").read_text(encoding="utf-8")
    assert "go_runtime_worker.py" in worker_text
    assert "RedirectStandardInput = true" in worker_text
    assert "RedirectStandardOutput = true" in worker_text

    main_text = (CLIENT / "scripts" / "Main.cs").read_text(encoding="utf-8")
    assert "ApplyResponsiveLayout" in main_text
    assert "ToolbarStrip" in main_text

    toolbar_text = (CLIENT / "scripts" / "ToolbarStrip.cs").read_text(encoding="utf-8")
    for label in ("开始", "Rogue", "Wiki", "虚手", "悔棋", "计算", "形势", "认输", "设置"):
        assert label in toolbar_text
    assert "FitToWidth" in toolbar_text

    scene_text = (CLIENT / "scenes" / "Main.tscn").read_text(encoding="utf-8")
    for label in ("围棋对弈场", "棋局控制台", "准备对局", "AI 待命", "卡牌编辑器"):
        assert label in scene_text
    for asset in (
        "res://assets/textures/ui-dark-wood-v1.png",
        "res://assets/icons/toolbar-tech",
        "CardIconTray",
    ):
        assert asset in scene_text + toolbar_text

    asset_files = [path for path in (CLIENT / "assets").rglob("*") if path.is_file()]
    assert asset_files, "Godot asset package is empty"
    web_runtime_suffixes = {".html", ".js", ".css"}
    leaked = [str(path) for path in asset_files if path.suffix.lower() in web_runtime_suffixes]
    assert not leaked, f"Godot asset package leaked web runtime files: {leaked}"

    print({"ok": True})


if __name__ == "__main__":
    main()
