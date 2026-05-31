from __future__ import annotations

from pathlib import Path
import sys


def ensure_repo_root(file_name: str) -> None:
    root = Path(file_name).resolve().parents[3]
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
