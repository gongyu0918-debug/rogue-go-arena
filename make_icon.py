"""Build Windows icon assets from the project app PNG."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def main() -> None:
    root = Path(__file__).resolve().parent
    source = root / "goai.png"
    image = Image.open(source).convert("RGBA")
    sizes = [256, 128, 64, 48, 32, 24, 16]
    frames = [
        image.resize((size, size), Image.Resampling.LANCZOS)
        for size in sizes
    ]
    frames[0].save(
        root / "goai.ico",
        format="ICO",
        sizes=[(size, size) for size in sizes],
        append_images=frames[1:],
    )
    (root / "static" / "assets").mkdir(parents=True, exist_ok=True)
    image.save(root / "static" / "assets" / "goai-favicon.png", format="PNG")
    print(f"Icon saved: {root / 'goai.ico'}")
    print(f"Favicon saved: {root / 'static' / 'assets' / 'goai-favicon.png'}")


if __name__ == "__main__":
    main()
