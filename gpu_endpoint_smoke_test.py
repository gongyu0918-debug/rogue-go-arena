from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import server as s
from app.runtime.gpu_info import CachedGpuInfo


class FakeEngineRuntime:
    cpu_mode = True


async def smoke_gpu_endpoint_uses_cached_detector_and_runtime_overrides() -> None:
    calls = []

    def detect_gpu():
        calls.append("detect")
        return {
            "name": "NVIDIA GeForce RTX 5070",
            "vram_mb": 12227,
            "tier": 4,
            "default_rank": "a5d",
            "slow_from": "p1d",
            "tier_label": "高端",
        }

    async def inline_executor(func, *args):
        return func(*args)

    original_detector = s._gpu_detector
    original_run_in_executor = s.run_in_executor
    original_engine_runtime = s.engine_runtime
    original_large_model = s.KATAGO_MODEL_LARGE
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            large_model = Path(temp_dir) / "model_large.bin.gz"
            large_model.write_text("", encoding="utf-8")

            s._gpu_detector = CachedGpuInfo(detect_gpu)
            s.run_in_executor = inline_executor
            s.engine_runtime = FakeEngineRuntime()
            s.KATAGO_MODEL_LARGE = large_model

            first = await s.get_gpu_info()
            second = await s.get_gpu_info()
    finally:
        s._gpu_detector = original_detector
        s.run_in_executor = original_run_in_executor
        s.engine_runtime = original_engine_runtime
        s.KATAGO_MODEL_LARGE = original_large_model

    assert calls == ["detect"]
    assert first == second
    assert first["name"] == "NVIDIA GeForce RTX 5070"
    assert first["cpu_mode"] is True
    assert first["large_model"] is True
    assert first["default_rank"] == "5k"
    assert first["slow_from"] == "1k"
    assert first["tier_label"] == "CPU模式"


async def main() -> None:
    await smoke_gpu_endpoint_uses_cached_detector_and_runtime_overrides()
    print("gpu endpoint smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
