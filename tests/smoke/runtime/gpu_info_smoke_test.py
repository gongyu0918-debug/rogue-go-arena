from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import subprocess
import tempfile
from pathlib import Path

from app.runtime.gpu_info import (
    CachedGpuInfo,
    apply_runtime_gpu_overrides,
    classify_gpu_tier,
    default_gpu_info,
    detect_gpu_info,
)


def check_output_factory(text: str):
    def fake_check_output(_args, timeout=None, creationflags=0):
        assert timeout == 10
        assert isinstance(creationflags, int)
        return text.encode("utf-8")

    return fake_check_output


def failing_check_output(_args, timeout=None, creationflags=0):
    raise subprocess.CalledProcessError(1, "nvidia-smi")


def main() -> int:
    high = detect_gpu_info(check_output_fn=check_output_factory("NVIDIA GeForce RTX 5070, 12227\n"))
    assert high["name"] == "NVIDIA GeForce RTX 5070"
    assert high["vram_mb"] == 12227
    assert high["tier"] == 4
    assert high["default_rank"] == "a5d"
    assert high["slow_from"] == "p1d"
    assert high["tier_label"] == "高端"

    fallback = detect_gpu_info(check_output_fn=check_output_factory("Generic CUDA Device, 8192\n"))
    assert fallback["tier"] == 3
    assert fallback["default_rank"] == "a3d"

    missing = detect_gpu_info(check_output_fn=failing_check_output)
    assert missing == default_gpu_info()

    detect_calls = []

    def fake_detect():
        detect_calls.append("detect")
        return {"name": "Cached GPU", "vram_mb": 4096}

    cached = CachedGpuInfo(fake_detect)
    first_cached = cached.detect()
    second_cached = cached.detect()
    assert first_cached is second_cached
    assert second_cached["name"] == "Cached GPU"
    assert detect_calls == ["detect"]

    cached.clear()
    assert cached.detect()["name"] == "Cached GPU"
    assert detect_calls == ["detect", "detect"]

    assert classify_gpu_tier("NVIDIA GeForce GTX 1050", 2048) == 2
    assert classify_gpu_tier("Unknown Adapter", 2048) == 1
    assert classify_gpu_tier("Unknown Adapter", 4096) == 2
    assert classify_gpu_tier("Unknown Adapter", 8192) == 3
    assert classify_gpu_tier("Unknown Adapter", 12288) == 4

    with tempfile.TemporaryDirectory() as tmp:
        large_model = Path(tmp) / "model_large.bin.gz"
        large_model.write_text("", encoding="utf-8")
        gpu_payload = apply_runtime_gpu_overrides(high, cpu_mode=False, large_model_path=large_model)
        assert gpu_payload["cpu_mode"] is False
        assert gpu_payload["large_model"] is True
        assert gpu_payload["default_rank"] == "a5d"

        cpu_payload = apply_runtime_gpu_overrides(high, cpu_mode=True, large_model_path=large_model)
        assert cpu_payload["cpu_mode"] is True
        assert cpu_payload["large_model"] is True
        assert cpu_payload["default_rank"] == "5k"
        assert cpu_payload["slow_from"] == "1k"
        assert cpu_payload["tier_label"] == "CPU模式"

    print("gpu info smoke test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
