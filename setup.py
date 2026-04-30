"""
rogue-go-arena setup helper.

Downloads the current Windows KataGo OpenCL + CPU binaries used by this
project, plus a default neural net model when the local runtime files are
missing.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path


BASE = Path(__file__).parent
KATAGO_DIR = BASE / "katago"
KATAGO_DIR.mkdir(exist_ok=True)

KATAGO_VERSION = "v1.16.4"
KATAGO_RELEASE_BASE = (
    f"https://github.com/lightvector/KataGo/releases/download/{KATAGO_VERSION}"
)
ENGINE_ASSETS = [
    {
        "label": "KataGo OpenCL (Windows x64)",
        "url": f"{KATAGO_RELEASE_BASE}/katago-{KATAGO_VERSION}-opencl-windows-x64.zip",
        "exe_name": "katago_opencl.exe",
    },
    {
        "label": "KataGo CPU Eigen (Windows x64)",
        "url": f"{KATAGO_RELEASE_BASE}/katago-{KATAGO_VERSION}-eigen-windows-x64.zip",
        "exe_name": "katago_cpu.exe",
    },
]

MODEL_URL = (
    "https://media.katago.org/kata1-b18c384nbt-s9996604160-d4316597426.bin.gz"
)
MODEL_URL_SMALL = (
    "https://media.katago.org/kata1-b28c512nbt-s8334800896-d3994671872.bin.gz"
)
MODEL_FILE = KATAGO_DIR / "model.bin.gz"

MINIMAL_OPENCL_CONFIG = """# rogue-go-arena generated fallback KataGo config
numSearchThreads = 6
maxVisits = 800
reportAnalysisWinratesAs = BLACK
logAllGTPCommunication = false
logSearchInfo = false
"""

MINIMAL_CPU_CONFIG = """# rogue-go-arena generated fallback KataGo CPU config
numSearchThreads = 4
maxVisits = 400
reportAnalysisWinratesAs = BLACK
logAllGTPCommunication = false
logSearchInfo = false
"""


def progress(count: int, block_size: int, total_size: int) -> None:
    if total_size <= 0:
        print(
            f"\r  Downloaded {count * block_size // 1024 // 1024} MB...",
            end="",
            flush=True,
        )
        return
    pct = min(100, count * block_size * 100 // total_size)
    mb = count * block_size // 1024 // 1024
    total_mb = total_size // 1024 // 1024
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
    print(f"\r  [{bar}] {pct}% ({mb}/{total_mb} MB)", end="", flush=True)


def download(url: str, dest: Path, desc: str) -> bool:
    print(f"\n📥 {desc}")
    print(f"   {url}")
    try:
        urllib.request.urlretrieve(url, dest, reporthook=progress)
        print()
        return True
    except Exception as exc:
        print(f"\n   ❌ 下载失败: {exc}")
        return False


def _safe_remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def _extract_engine_zip(zip_path: Path, *, exe_name: str) -> bool:
    staging_dir = KATAGO_DIR / "_extract_tmp"
    _safe_remove(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    keep_names = {
        exe_name,
        "cacert.pem",
        "README.txt",
        "README.md",
    }
    keep_suffixes = {".dll"}

    extracted_any = False
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.infolist():
                member_path = Path(member.filename)
                if member.is_dir():
                    continue
                filename = member_path.name
                should_keep = (
                    filename == "katago.exe"
                    or filename in keep_names
                    or member_path.parts[:1] == ("KataGoData",)
                    or filename.endswith(tuple(keep_suffixes))
                )
                if not should_keep:
                    continue
                zf.extract(member, staging_dir)
                extracted_any = True

        if not extracted_any:
            print("❌ 压缩包里没有找到可用的 KataGo 文件")
            return False

        for path in staging_dir.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(staging_dir)
            filename = path.name
            if filename == "katago.exe":
                target = KATAGO_DIR / exe_name
            elif rel.parts[:1] == ("KataGoData",):
                target = KATAGO_DIR / rel
                target.parent.mkdir(parents=True, exist_ok=True)
            else:
                target = KATAGO_DIR / filename
            shutil.move(str(path), str(target))
        return (KATAGO_DIR / exe_name).exists()
    finally:
        _safe_remove(staging_dir)
        zip_path.unlink(missing_ok=True)


def ensure_configs() -> None:
    config_path = KATAGO_DIR / "config.cfg"
    cpu_config_path = KATAGO_DIR / "config_cpu.cfg"
    if not config_path.exists():
        config_path.write_text(MINIMAL_OPENCL_CONFIG, encoding="utf-8")
        print(f"✅ 已生成 OpenCL 配置: {config_path}")
    else:
        print(f"✅ OpenCL 配置已存在: {config_path}")
    if not cpu_config_path.exists():
        cpu_config_path.write_text(MINIMAL_CPU_CONFIG, encoding="utf-8")
        print(f"✅ 已生成 CPU 配置: {cpu_config_path}")
    else:
        print(f"✅ CPU 配置已存在: {cpu_config_path}")


def install_engines() -> bool:
    overall_ok = True
    for asset in ENGINE_ASSETS:
        exe_path = KATAGO_DIR / asset["exe_name"]
        if exe_path.exists():
            print(f"✅ {asset['label']} 已存在: {exe_path}")
            continue
        zip_path = KATAGO_DIR / f"{asset['exe_name']}.zip"
        if not download(asset["url"], zip_path, f"下载 {asset['label']}"):
            overall_ok = False
            print(f"   手动下载后请将 {asset['exe_name']} 放到: {KATAGO_DIR}")
            continue
        print(f"📦 解压 {asset['label']} ...")
        if _extract_engine_zip(zip_path, exe_name=asset["exe_name"]):
            print(f"✅ {asset['label']} 安装成功: {exe_path}")
        else:
            overall_ok = False
            print(f"❌ {asset['label']} 解压失败，请手动安装")
    return overall_ok


def install_model() -> bool:
    if MODEL_FILE.exists() and MODEL_FILE.stat().st_size > 1_000_000:
        print(f"✅ 模型已存在: {MODEL_FILE}")
        return True

    urls = [
        (MODEL_URL, "kata1-b18c384nbt (默认模型, ~340MB)"),
        (MODEL_URL_SMALL, "kata1-b28c512nbt (备用模型)"),
    ]
    for url, desc in urls:
        tmp = KATAGO_DIR / "model_tmp.bin.gz"
        if download(url, tmp, f"下载权重文件 {desc}"):
            shutil.move(str(tmp), str(MODEL_FILE))
            print(f"✅ 模型下载成功: {MODEL_FILE}")
            return True

    print("\n⚠ 自动下载失败，请手动下载模型:")
    print("   访问: https://katagotraining.org/networks/")
    print(f"   下载任意 .bin.gz 文件到: {KATAGO_DIR}")
    print("   重命名为 model.bin.gz")
    return False


def check_dependencies() -> None:
    print("🔍 检查 Python 依赖...")
    missing: list[str] = []
    for pkg in ["fastapi", "uvicorn", "websockets"]:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            missing.append(pkg)

    if not missing:
        print("   ✅ 所有依赖已安装")
        return

    print(f"   安装缺少的包: {' '.join(missing)}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])


def main() -> None:
    print("=" * 60)
    print("  rogue-go-arena 安装向导 — KataGo OpenCL / CPU")
    print("=" * 60)

    check_dependencies()
    ensure_configs()
    engines_ok = install_engines()
    model_ok = install_model()

    print("\n" + "=" * 60)
    if engines_ok and model_ok:
        print("🎉 安装完成！运行以下命令启动:")
        print(f"   cd {BASE}")
        print("   start.bat")
        print("   或 python server.py")
        print("   然后打开浏览器访问: http://localhost:8000")
    else:
        print("⚠ 安装未完成，请检查以上错误信息")
        if not engines_ok:
            print("\n手动安装 KataGo:")
            for asset in ENGINE_ASSETS:
                print(f"  - {asset['label']}: {asset['url']}")
            print(f"  解压后将可执行文件与 DLL 放到: {KATAGO_DIR}")
        if not model_ok:
            print("\n手动下载模型:")
            print("  1. 访问: https://katagotraining.org/networks/")
            print(f"  2. 下载 .bin.gz 文件到 {KATAGO_DIR}")
            print("  3. 重命名为 model.bin.gz")
    print("=" * 60)


if __name__ == "__main__":
    main()
