"""
GoAI Setup — Downloads KataGo (CUDA) and the neural network model
Run once before starting the server.
"""
import os
import sys
import urllib.request
import zipfile
import gzip
import shutil
from pathlib import Path

BASE = Path(__file__).parent
KATAGO_DIR = BASE / "katago"
KATAGO_DIR.mkdir(exist_ok=True)

# ─── KataGo release for Windows + CUDA 12 ────────────────────────────────────
# RTX 5090 with CUDA 13.2 driver is backward-compatible with CUDA 12.x binaries
KATAGO_VERSION = "v1.15.3"
KATAGO_ZIP_URL = (
    f"https://github.com/lightvector/KataGo/releases/download/{KATAGO_VERSION}/"
    f"katago-{KATAGO_VERSION}-cuda12-windows-x64.zip"
)
KATAGO_EXE = KATAGO_DIR / "katago.exe"

# ─── Model — kata1-b18c384nbt (strong & fast on modern GPU) ──────────────────
# Download from KataGo's model page (best public weight)
MODEL_URL = (
    "https://media.katago.org/kata1-b18c384nbt-s9996604160-d4316597426.bin.gz"
)
MODEL_FILE = KATAGO_DIR / "model.bin.gz"

# Fallback: smaller but still strong model
MODEL_URL_SMALL = (
    "https://media.katago.org/kata1-b28c512nbt-s8334800896-d3994671872.bin.gz"
)


def progress(count, block_size, total_size):
    if total_size <= 0:
        print(f"\r  Downloaded {count*block_size//1024//1024} MB...", end="", flush=True)
        return
    pct = min(100, count * block_size * 100 // total_size)
    mb = count * block_size // 1024 // 1024
    total_mb = total_size // 1024 // 1024
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
    print(f"\r  [{bar}] {pct}% ({mb}/{total_mb} MB)", end="", flush=True)


def download(url, dest, desc):
    print(f"\n📥 {desc}")
    print(f"   {url}")
    try:
        urllib.request.urlretrieve(url, dest, reporthook=progress)
        print()
        return True
    except Exception as e:
        print(f"\n   ❌ 下载失败: {e}")
        return False


def install_katago():
    if KATAGO_EXE.exists():
        print(f"✅ KataGo 已存在: {KATAGO_EXE}")
        return True

    zip_path = KATAGO_DIR / "katago.zip"
    if not download(KATAGO_ZIP_URL, zip_path, "下载 KataGo (CUDA 12, Windows x64)"):
        print("\n⚠  请手动下载 KataGo:")
        print(f"   {KATAGO_ZIP_URL}")
        print(f"   解压后将 katago.exe 放到: {KATAGO_DIR}")
        return False

    print("📦 解压 KataGo...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            if name.endswith("katago.exe"):
                zf.extract(name, KATAGO_DIR)
                # Move to correct location if nested
                extracted = KATAGO_DIR / name
                if extracted != KATAGO_EXE:
                    shutil.move(str(extracted), str(KATAGO_EXE))
                break

    zip_path.unlink(missing_ok=True)

    if KATAGO_EXE.exists():
        print(f"✅ KataGo 安装成功: {KATAGO_EXE}")
        return True
    else:
        print("❌ 找不到 katago.exe，请手动安装")
        return False


def install_model():
    if MODEL_FILE.exists() and MODEL_FILE.stat().st_size > 1_000_000:
        print(f"✅ 模型已存在: {MODEL_FILE}")
        return True

    # Try primary model URL
    urls = [
        (MODEL_URL, "kata1-b18c384nbt (强力模型, ~340MB)"),
        (MODEL_URL_SMALL, "kata1-b28c512nbt (备用模型)"),
    ]

    for url, desc in urls:
        tmp = KATAGO_DIR / "model_tmp.bin.gz"
        if download(url, tmp, f"下载权重文件 {desc}"):
            shutil.move(str(tmp), str(MODEL_FILE))
            print(f"✅ 模型下载成功: {MODEL_FILE}")
            return True

    print("\n⚠  自动下载失败，请手动下载模型:")
    print("   访问: https://katagotraining.org/networks/")
    print("   下载任意 .bin.gz 文件到:", MODEL_DIR)
    print("   重命名为 model.bin.gz")
    return False


def check_dependencies():
    print("🔍 检查 Python 依赖...")
    missing = []
    for pkg in ["fastapi", "uvicorn", "websockets"]:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"   安装缺少的包: {' '.join(missing)}")
        os.system(f"{sys.executable} -m pip install {' '.join(missing)}")
    else:
        print("   ✅ 所有依赖已安装")


def write_config():
    config_path = KATAGO_DIR / "config.cfg"
    if config_path.exists():
        print(f"✅ 配置文件已存在: {config_path}")
        return

    config = """# KataGo GTP Configuration — RTX 5090 Optimized

numNNServerThreadsPerModel = 2
cudaUseFP16 = true
cudaUseNHWC = true

maxVisits = 800
numSearchThreads = 8

reportAnalysisWinratesAs = BLACK
logAllGTPCommunication = false
logSearchInfo = false
"""
    config_path.write_text(config)
    print(f"✅ 配置文件已生成: {config_path}")


def main():
    print("=" * 60)
    print("  GoAI 安装向导 — KataGo + RTX 5090")
    print("=" * 60)

    check_dependencies()
    write_config()
    katago_ok = install_katago()
    model_ok = install_model()

    print("\n" + "=" * 60)
    if katago_ok and model_ok:
        print("🎉 安装完成！运行以下命令启动:")
        print(f"   cd {BASE}")
        print("   python server.py")
        print("   然后打开浏览器访问: http://localhost:8000")
    else:
        print("⚠  安装未完成，请检查以上错误信息")
        if not katago_ok:
            print(f"\n手动安装 KataGo:")
            print(f"  1. 下载: {KATAGO_ZIP_URL}")
            print(f"  2. 解压 katago.exe 到: {KATAGO_DIR}")
        if not model_ok:
            print(f"\n手动下载模型:")
            print(f"  1. 访问: https://katagotraining.org/networks/")
            print(f"  2. 下载 .bin.gz 文件到 {KATAGO_DIR}")
            print(f"  3. 重命名为 model.bin.gz")
    print("=" * 60)


if __name__ == "__main__":
    main()
