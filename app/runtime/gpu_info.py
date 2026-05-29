from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from app.config.gpu_tiers import GPU_TIER_PATTERNS, GPU_TIERS


_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def default_gpu_info() -> dict[str, Any]:
    return {
        "name": "Unknown",
        "vram_mb": 0,
        "tier": 1,
        "default_rank": "3k",
        "slow_from": "1k",
        "tier_label": "未知",
    }


def detect_gpu_info(
    *,
    check_output_fn: Callable[..., bytes] = subprocess.check_output,
    tier_patterns: Sequence[tuple[str, int]] = GPU_TIER_PATTERNS,
    tiers: dict[int, tuple[str, str, str]] = GPU_TIERS,
) -> dict[str, Any]:
    result = default_gpu_info()
    try:
        out = check_output_fn(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            timeout=10,
            creationflags=_CREATE_NO_WINDOW,
        ).decode("utf-8", errors="replace").strip()
        if not out:
            return result

        parts = out.split("\n")[0].split(",")
        gpu_name = parts[0].strip()
        vram = int(float(parts[1].strip())) if len(parts) > 1 else 0
        tier = classify_gpu_tier(gpu_name, vram, tier_patterns=tier_patterns)
        rank, slow_from, label = tiers[tier]
        result.update({
            "name": gpu_name,
            "vram_mb": vram,
            "tier": tier,
            "default_rank": rank,
            "slow_from": slow_from,
            "tier_label": label,
        })
    except Exception:
        pass
    return result


def classify_gpu_tier(
    gpu_name: str,
    vram_mb: int,
    *,
    tier_patterns: Sequence[tuple[str, int]] = GPU_TIER_PATTERNS,
) -> int:
    for pattern, tier in tier_patterns:
        if re.search(pattern, gpu_name, re.IGNORECASE):
            return tier
    if vram_mb >= 10000:
        return 4
    if vram_mb >= 6000:
        return 3
    if vram_mb >= 3000:
        return 2
    return 1


def apply_runtime_gpu_overrides(
    gpu_info: dict[str, Any],
    *,
    cpu_mode: bool,
    large_model_path: Path,
) -> dict[str, Any]:
    result = dict(gpu_info)
    result["cpu_mode"] = cpu_mode
    result["large_model"] = large_model_path.exists()
    if cpu_mode:
        result["default_rank"] = "5k"
        result["slow_from"] = "1k"
        result["tier_label"] = "CPU模式"
    return result
