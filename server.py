"""
GoAI Server - KataGo-powered Go AI with FastAPI WebSocket backend
"""
import argparse
import asyncio
import json
import random
import subprocess
import threading
import queue
import re
import socket
import time
import os
import sys
from collections import deque
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
import uvicorn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

# ─── CLI flags ───────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--no-katago", action="store_true",
                    help="Disable KataGo (free-play / two-player only)")
args, _ = parser.parse_known_args()
NO_KATAGO = args.no_katago

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent.parent  # GoAI_Server/GoAI_Server.exe -> GoAI/
else:
    BASE_DIR = Path(__file__).parent
USER_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(BASE_DIR))) / "GoAI"
USER_KATAGO_DIR = USER_DATA_DIR / "katago"
USER_KATAGO_HOME = USER_KATAGO_DIR / "KataGoData"
USER_RUNTIME_CONFIG_DIR = USER_KATAGO_DIR / "runtime"
SERVER_REV = "20260329-rogue-two-player-ai"
KATAGO_EXE = BASE_DIR / "katago" / "katago.exe"             # CUDA build (legacy/optional)
KATAGO_CUDA_EXE = BASE_DIR / "katago" / "katago_cuda.exe"   # CUDA (downloaded upgrade)
KATAGO_OPENCL_EXE = BASE_DIR / "katago" / "katago_opencl.exe"  # OpenCL (any GPU)
KATAGO_CPU_EXE = BASE_DIR / "katago" / "katago_cpu.exe"      # CPU (no GPU needed)
KATAGO_MODEL_LARGE = BASE_DIR / "katago" / "model_large.bin.gz"  # Upgraded large model (b28/b40)
KATAGO_MODEL = BASE_DIR / "katago" / "model.bin.gz"             # Default bundled model
KATAGO_MODEL_SMALL = BASE_DIR / "katago" / "model_b18.bin.gz"   # Compact model (b18)
USER_KATAGO_CUDA_EXE = USER_KATAGO_DIR / "katago_cuda.exe"
USER_KATAGO_MODEL_LARGE = USER_KATAGO_DIR / "model_large.bin.gz"
KATAGO_CONFIG = BASE_DIR / "katago" / "config.cfg"
KATAGO_CPU_CONFIG = BASE_DIR / "katago" / "config_cpu.cfg"
STATIC_DIR = BASE_DIR / "static"
CPU_MODE = False  # Set True at startup if using CPU engine
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000


def log(message: str):
    print(message, flush=True)


def _ensure_user_katago_dirs():
    for path in (USER_DATA_DIR, USER_KATAGO_DIR, USER_KATAGO_HOME, USER_RUNTIME_CONFIG_DIR):
        path.mkdir(parents=True, exist_ok=True)


def _runtime_config_path(source_config: Path) -> Path:
    _ensure_user_katago_dirs()
    runtime_path = USER_RUNTIME_CONFIG_DIR / f"{source_config.stem}_runtime.cfg"
    content = source_config.read_text(encoding="utf-8", errors="ignore")
    home_dir = USER_KATAGO_HOME.as_posix()
    if re.search(r"(?m)^\s*#?\s*homeDataDir\s*=", content):
        content = re.sub(
            r"(?m)^\s*#?\s*homeDataDir\s*=.*$",
            f"homeDataDir = {home_dir}",
            content,
            count=1,
        )
    else:
        content = content.rstrip() + f"\n\nhomeDataDir = {home_dir}\n"
    runtime_path.write_text(content, encoding="utf-8")
    return runtime_path

# ─── Rank tables ─────────────────────────────────────────────────────────────
RANK_VISITS = {
    "18k": 2,   "17k": 3,   "16k": 5,   "15k": 8,   "14k": 12,
    "13k": 18,  "12k": 28,  "11k": 40,  "10k": 60,
    "9k":  90,  "8k":  130, "7k":  180, "6k":  260,  "5k":  380,
    "4k":  550, "3k":  800, "2k":  1100, "1k": 1500,
    "a1d": 2200,  "a2d": 3500,  "a3d": 5500,  "a4d": 9000,
    "a5d": 12000, "a6d": 15000, "a7d": 18000, "a8d": 20000,
    "a9d": 22000,
    "p1d": 24000, "p2d": 26000, "p3d": 28000,
    "p4d": 30000, "p5d": 32000, "p6d": 34000,
    "p7d": 36000, "p8d": 38000,
    "p9d": 0,
}

RANK_LABELS = {
    "18k": "18级", "17k": "17级", "16k": "16级", "15k": "15级",
    "14k": "14级", "13k": "13级", "12k": "12级", "11k": "11级",
    "10k": "10级", "9k": "9级", "8k": "8级", "7k": "7级",
    "6k": "6级", "5k": "5级", "4k": "4级", "3k": "3级",
    "2k": "2级", "1k": "1级",
    "a1d": "业余1段", "a2d": "业余2段", "a3d": "业余3段",
    "a4d": "业余4段", "a5d": "业余5段", "a6d": "业余6段",
    "a7d": "业余7段", "a8d": "业余8段", "a9d": "业余9段",
    "p1d": "职业一段", "p2d": "职业二段", "p3d": "职业三段",
    "p4d": "职业四段", "p5d": "职业五段", "p6d": "职业六段",
    "p7d": "职业七段", "p8d": "职业八段", "p9d": "职业九段",
}

MAX_GAME_VISITS = 20000   # Hard cap on visits per move
ROGUE_MAX_VISITS = 800    # Cap for rogue mode (chaotic board, no need for deep search)
ULTIMATE_MAX_VISITS = 400 # Cap for ultimate mode (20 moves, effects dominate)
CPU_MAX_VISITS = 500      # Hard cap for CPU mode (keep response < 5s)

# Rogue mode tuning: keep the cards impactful without turning every game into
# a scripted auto-win. These are intentionally a bit generous to emphasize the
# "fun modifier" feel over perfect balance.
ROGUE_DICE_PASS_CHANCE = 0.14
ROGUE_SLIP_CHANCE = 0.38
ROGUE_MIRROR_CHANCE = 0.30
ROGUE_NERF_FACTOR = 0.40
ROGUE_FOG_MASK_RADIUS = 1
ROGUE_GRAVITY_AI_MOVES = 5
ROGUE_LOWLINE_AI_MOVES = 6
ROGUE_SHADOW_AI_MOVE_INDEXES = {1, 2, 3}
ROGUE_SUBOPTIMAL_AI_MOVES = 10
ROGUE_TIME_PRESS_MAX_TIME = 0.7
ROGUE_TIME_PRESS_MAX_VISITS = 500
ROGUE_FOOLISH_FILL_COUNT = 1
ULTIMATE_FOOLISH_FILL_COUNT = 20
ULTIMATE_FOOLISH_CHAIN_DELAY = 1.0
ROGUE_HANDICAP_REQUIRED_PASSES = 1
ROGUE_HANDICAP_BONUS_INTERVAL = 4
ROGUE_HANDICAP_MAX_BONUSES = 4
ROGUE_JOSEKI_TARGET_COUNT = 7
ROGUE_JOSEKI_REQUIRED_HITS = 3
ROGUE_GODHAND_FILL_COUNT = 5
ROGUE_NO_REGRET_CHANCE = 0.14
ROGUE_QUICKTHINK_FIRST_SECONDS = 3
ROGUE_QUICKTHINK_SECOND_SECONDS = 2

# Ultimate mode tuning: prioritize spectacle and reliable payoff.
ULTIMATE_CHAIN_EXTRA_TURN_CHANCE = 0.65
ULTIMATE_WILDGROW_MAX_GROWTH = 4
ULTIMATE_METEOR_DESTROY_COUNT = 5
ULTIMATE_QUANTUM_PLACE_COUNT = 5
ULTIMATE_TIMEWARP_TRIGGER_CHANCE = 0.85
ULTIMATE_TERRITORY_RADIUS = 4
ULTIMATE_JOSEKI_TARGET_COUNT = 7
ULTIMATE_JOSEKI_REQUIRED_HITS = 3
ULTIMATE_JOSEKI_BONUS_STONES = 12
ULTIMATE_GODHAND_FILL_COUNT = 50
ULTIMATE_QUICKTHINK_SECONDS = 5

ROGUE_FEATURED_CARDS = {
    "god_hand",
    "sansan_trap",
    "corner_helper",
    "sanrensei",
    "no_regret",
    "quickthink",
    "foolish_wisdom",
}

TWO_PLAYER_ROGUE_POOL = [
    "erosion",
    "sprout",
    "joseki_ocd",
    "god_hand",
    "sansan_trap",
    "corner_helper",
    "sanrensei",
    "foolish_wisdom",
]

AI_ROGUE_POOL = [
    "blackhole",
    "golden_corner",
    "fog",
    "sansan_trap",
]

ULTIMATE_FEATURED_CARDS = {
    "joseki_burst",
    "god_hand",
    "corner_helper",
    "sanrensei",
    "quickthink",
    "foolish_wisdom",
}

# Maximum seconds KataGo may think per move (safety net)
MAX_MOVE_TIME = 12.0

# Opening phase: first N total moves (both sides) use a hard visit cap
# so the response is nearly instant (neural net raw policy is already strong)
OPENING_MOVE_THRESHOLD = 50   # first ~25 moves per side
OPENING_MAX_VISITS = 500      # ~2-3s on most GPUs — still superhuman


def get_game_visits(level: str, move_count: int = -1,
                    mode: str = "normal") -> int:
    """Cap visits so even the strongest rank finishes within MAX_MOVE_TIME.
    In the opening, use a hard cap for instant response.
    mode: 'normal', 'rogue', or 'ultimate'."""
    raw = RANK_VISITS.get(level, 800)
    if raw == 0:
        visits = MAX_GAME_VISITS   # p9d: use the cap, not unlimited
    else:
        visits = min(raw, MAX_GAME_VISITS)
    # Rogue / Ultimate: cap visits — chaotic boards don't need deep search
    if mode == "rogue":
        visits = min(visits, ROGUE_MAX_VISITS)
    elif mode == "ultimate":
        visits = min(visits, ULTIMATE_MAX_VISITS)
    # CPU mode: hard cap to keep response time acceptable
    if CPU_MODE:
        visits = min(visits, CPU_MAX_VISITS)
    # Opening speed: hard cap — NN raw policy already plays strong openings
    if 0 <= move_count < OPENING_MOVE_THRESHOLD and visits > OPENING_MAX_VISITS:
        visits = OPENING_MAX_VISITS
    return visits


# ─── Rogue mode cards ────────────────────────────────────────────────────────
ROGUE_CARDS = {
    "tengen": {
        "name": "天元",
        "desc": "AI 前 2 手优先下天元或星位",
        "icon": "◎",
    },
    "dice": {
        "name": "投骰子",
        "desc": "AI 有 14% 概率直接虚手",
        "icon": "🎲",
    },
    "erosion": {
        "name": "蚕食",
        "desc": "每提掉 1 颗敌子，贴目额外波动 2 目",
        "icon": "🪲",
    },
    "puppet": {
        "name": "傀儡术",
        "desc": "主动使用 1 次，让 AI 按你指定的位置落子",
        "icon": "🎭",
        "uses": 1,
    },
    "seal": {
        "name": "封印术",
        "desc": "选择 3 个点位，本局 AI 不可落子",
        "icon": "🔒",
    },
    "twin": {
        "name": "连击",
        "desc": "主动使用 1 次，本回合你可连续落两手",
        "icon": "⚡",
        "uses": 1,
    },
    "nerf": {
        "name": "弱化",
        "desc": "AI 搜索量降低 60%",
        "icon": "📉",
    },
    "komi_relief": {
        "name": "贴目减负",
        "desc": "贴目从 7.5 降到 2.5",
        "icon": "⚖️",
    },
    "time_press": {
        "name": "时间压制",
        "desc": "AI 每手思考最多 0.7 秒",
        "icon": "⏱️",
    },
    "lowline": {
        "name": "低空飞行",
        "desc": "AI 前 6 手更偏向二三路线",
        "icon": "🪁",
    },
    "suboptimal": {
        "name": "次优之选",
        "desc": "AI 前 10 手从第 3 到第 5 优点位中落子",
        "icon": "🥈",
    },
    "mirror": {
        "name": "镜像",
        "desc": "AI 有 30% 概率镜像你的上一手",
        "icon": "🪞",
    },
    "slip": {
        "name": "手滑了",
        "desc": "AI 有 38% 概率滑到目标相邻点",
        "icon": "🤏",
    },
    "blackhole": {
        "name": "黑洞",
        "desc": "棋盘中央 13 路区域禁止 AI 落子",
        "icon": "🕳️",
    },
    "exchange": {
        "name": "乾坤挪移",
        "desc": "主动使用 1 次，本回合让 AI 虚手并由你继续落子",
        "icon": "🔄",
        "uses": 1,
    },
    "fog": {
        "name": "迷雾",
        "desc": "每次 AI 落子前刷新 1 个 3x3 遮罩，AI 不可落入",
        "icon": "🌫️",
    },
    "gravity": {
        "name": "引力",
        "desc": "AI 前 5 手更偏向星位",
        "icon": "🧲",
    },
    "golden_corner": {
        "name": "黄金角",
        "desc": "随机封锁一个角部 4x4 区域，AI 不可落子",
        "icon": "🏆",
    },
    "sansan": {
        "name": "三三开局",
        "desc": "AI 前 4 手优先下三三，之后 4 手避开角部 5x5",
        "icon": "◣",
    },
    "shadow": {
        "name": "影子",
        "desc": "AI 前 3 手倾向贴着自己的上一手下",
        "icon": "👤",
    },
    "sprout": {
        "name": "萌芽",
        "desc": "每成功提掉 1 子，随机长出 1 颗己方棋子",
        "icon": "🌱",
    },
    "joseki_ocd": {
        "name": "定式强迫症",
        "desc": "点亮 7 个随机点位，命中 3 个后自动补满剩余 4 点",
        "icon": "📐",
    },
    "handicap_quest": {
        "name": "让子任务",
        "desc": "主动虚手 1 次；每 4 手额外奖励 1 次 AI 虚手",
        "icon": "🎁",
    },
    "god_hand": {
        "name": "神之一手",
        "desc": "踩中隐藏 3x3 菱形区后，在 5x5 范围爆发 5 颗同色棋",
        "icon": "✨",
    },
    "sansan_trap": {
        "name": "三三是陷阱",
        "desc": "若 AI 开局下在任意角三三，则旁边生成 3 颗己方棋子",
        "icon": "🪤",
    },
    "corner_helper": {
        "name": "守角辅助器",
        "desc": "角部 5x5 已有 2 颗己子时，再补出 2 颗角部支援棋",
        "icon": "🏯",
    },
    "sanrensei": {
        "name": "三连星",
        "desc": "前三手都下在星位时，额外生成 3 颗己方棋子",
        "icon": "⭐",
    },
    "no_regret": {
        "name": "我不悔棋",
        "desc": "禁用悔棋；每手有 14% 概率补 1 颗次优点同色棋",
        "icon": "🚫",
    },
    "quickthink": {
        "name": "快速思考",
        "desc": "落子限时 3 秒，成功落子后可在 2 秒内再下一手",
        "icon": "⚡",
    },
    "foolish_wisdom": {
        "name": "大智若愚",
        "desc": "摆出孤立 L 形愚形时，在 5x5 范围随机长出 1 颗己子",
        "icon": "🧩",
    },
}


def pick_rogue_choices(n: int = 3, pool: Optional[list[str]] = None) -> list[str]:
    """Pick n random unique card IDs."""
    import time
    rng = random.Random(time.time_ns())
    keys = list(pool or ROGUE_CARDS.keys())
    rng.shuffle(keys)
    choices = keys[:n]
    if choices and not any(card in ROGUE_FEATURED_CARDS for card in choices):
        featured_pool = [card for card in keys if card in ROGUE_FEATURED_CARDS]
        if featured_pool:
            choices[-1] = rng.choice(featured_pool)
    unique_choices = []
    for card in choices:
        if card not in unique_choices:
            unique_choices.append(card)
    for card in keys:
        if len(unique_choices) >= n:
            break
        if card not in unique_choices:
            unique_choices.append(card)
    return unique_choices[:n]


def pick_ai_rogue_card(exclude: Optional[list[str]] = None) -> str:
    import time
    rng = random.Random(time.time_ns())
    pool = [k for k in AI_ROGUE_POOL if k not in (exclude or [])]
    return rng.choice(pool or AI_ROGUE_POOL)


# ─── Ultimate Rogue mode cards (大招模式) ────────────────────────────────────
ULTIMATE_CARDS = {
    "chain": {
        "name": "连珠棋",
        "desc": "玩家每手有 65% 概率再下一手",
        "icon": "🔥",
    },
    "proliferate": {
        "name": "无限增殖",
        "desc": "落子后在 5x5 范围额外生成 5 颗同色棋",
        "icon": "🌸",
    },
    "double": {
        "name": "双刀流",
        "desc": "你的回合固定连续下 2 手",
        "icon": "⚔️",
    },
    "wildgrow": {
        "name": "狂野生长",
        "desc": "随机 4 颗己子继续向周围蔓延生长",
        "icon": "🌿",
    },
    "rejection": {
        "name": "排异反应",
        "desc": "落点 3x3 内的敌子会被推开或摧毁",
        "icon": "💥",
    },
    "territory": {
        "name": "绝对领地",
        "desc": "落点周围 4 格范围形成禁入领地",
        "icon": "🛡️",
    },
    "shadow_clone": {
        "name": "影分身",
        "desc": "在对称位置额外生成一颗分身棋子",
        "icon": "👥",
    },
    "plague": {
        "name": "瘟疫",
        "desc": "落点 3x3 范围内敌子全部转化成己子",
        "icon": "☣️",
    },
    "meteor": {
        "name": "陨石",
        "desc": "随机摧毁 5 颗对方棋子",
        "icon": "☄️",
    },
    "quantum": {
        "name": "量子纠缠",
        "desc": "随机在全盘生成 5 颗同色棋子",
        "icon": "🌀",
    },
    "devour": {
        "name": "吞噬",
        "desc": "清空落点 5x5 范围内的全部敌子",
        "icon": "🦷",
    },
    "timewarp": {
        "name": "时空裂缝",
        "desc": "有 85% 概率抹去对手最近 2 手",
        "icon": "🕰️",
    },
    "blackout": {
        "name": "天崩地裂",
        "desc": "清除落点十字范围内的所有敌子",
        "icon": "🌋",
    },
    "magnet": {
        "name": "磁力吸附",
        "desc": "己方棋子朝落点聚拢并碾碎路径上的敌子",
        "icon": "🧲",
    },
    "necro": {
        "name": "亡灵召唤",
        "desc": "生成 3 颗己棋，并转化 2 颗敌棋",
        "icon": "💀",
    },
    "wall": {
        "name": "城墙",
        "desc": "在整行或整列筑起一面棋墙",
        "icon": "🧱",
    },
    "joseki_burst": {
        "name": "定式爆发",
        "desc": "命中定式点后补满剩余点，并额外爆发 12 颗同色棋",
        "icon": "📐",
    },
    "god_hand": {
        "name": "神之一手",
        "desc": "踩中隐藏 5x5 菱形区后，清空敌棋并填充 50 颗己棋",
        "icon": "✨",
    },
    "corner_helper": {
        "name": "守角辅助器",
        "desc": "满足角部条件后，8x8 边界铺满己棋并清空范围敌子",
        "icon": "🏯",
    },
    "sanrensei": {
        "name": "三连星",
        "desc": "前三手全是星位时，引爆全盘星位势力",
        "icon": "⭐",
    },
    "quickthink": {
        "name": "快速思考",
        "desc": "5 秒内可任意连续落子，结束后 AI 再读盘",
        "icon": "⚡",
    },
    "foolish_wisdom": {
        "name": "大智若愚",
        "desc": "检测到愚形后，全盘连锁生成 20 颗己棋直到不再触发",
        "icon": "🧩",
    },
}


# AI only gets simple brute-force cards (no turn manipulation or spatial mechanics)
AI_ULTIMATE_POOL = [
    "proliferate", "meteor", "quantum", "devour", "necro",
    "wall", "blackout", "wildgrow", "plague",
]


def pick_ultimate_choices(n: int = 3, exclude: list = None) -> list[str]:
    """Pick n random unique ultimate card IDs, excluding given keys."""
    import time
    rng = random.Random(time.time_ns())
    keys = [k for k in ULTIMATE_CARDS if k not in (exclude or [])]
    rng.shuffle(keys)
    choices = keys[:n]
    if choices and not any(card in ULTIMATE_FEATURED_CARDS for card in choices):
        featured_pool = [card for card in keys if card in ULTIMATE_FEATURED_CARDS]
        if featured_pool:
            choices[-1] = rng.choice(featured_pool)
    unique_choices = []
    for card in choices:
        if card not in unique_choices:
            unique_choices.append(card)
    for card in keys:
        if len(unique_choices) >= n:
            break
        if card not in unique_choices:
            unique_choices.append(card)
    return unique_choices[:n]


def pick_ai_ultimate_card(exclude: list = None) -> str:
    """Pick 1 random AI card from the simple brute-force pool."""
    import time
    rng = random.Random(time.time_ns())
    pool = [k for k in AI_ULTIMATE_POOL if k not in (exclude or [])]
    return rng.choice(pool)


def get_access_urls(port: int = SERVER_PORT) -> dict:
    lan_ips = set()
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = item[4][0]
            if ip and not ip.startswith("127."):
                lan_ips.add(ip)
    except OSError:
        pass

    # Use a UDP probe to discover the primary outbound interface IP when
    # getaddrinfo only returns localhost on some Windows setups.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                lan_ips.add(ip)
    except OSError:
        pass

    return {
        "local": [
            f"http://localhost:{port}",
            f"http://127.0.0.1:{port}",
        ],
        "lan": [f"http://{ip}:{port}" for ip in sorted(lan_ips)],
    }


def coord_to_gtp(x, y, size=19):
    cols = "ABCDEFGHJKLMNOPQRST"
    return f"{cols[x]}{size - y}"


def gtp_to_coord(gtp, size=19):
    cols = "ABCDEFGHJKLMNOPQRST"
    if gtp.upper() == "PASS":
        return None
    try:
        col = cols.index(gtp[0].upper())
        row = size - int(gtp[1:])
        if 0 <= col < size and 0 <= row < size:
            return (col, row)
    except (ValueError, IndexError):
        print(f"[GTP] Invalid coord: {gtp!r}")
    return None


# ─── KataGo engine ───────────────────────────────────────────────────────────
class KataGoEngine:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.response_queue = queue.Queue()
        self.analysis_lines = []
        self.ownership_data: list = []
        self.analysis_lock = threading.Lock()
        self.command_lock = threading.Lock()
        self.is_analyzing = False
        self.current_visits = 800
        self.ready = False
        self.stderr_lines = []
        self.stderr_callback = None
        self.last_stderr_time = 0.0

    def start(self, exe=None, config=None, model=None,
              startup_timeout: float = 120.0,
              stall_timeout: float = 45.0,
              stderr_callback=None):
        _exe = exe or KATAGO_EXE
        _cfg = config or KATAGO_CONFIG
        _model = model or KATAGO_MODEL
        if not Path(_exe).exists():
            raise FileNotFoundError(f"KataGo not found: {_exe}")
        if not Path(_model).exists():
            raise FileNotFoundError(f"Model not found: {_model}")

        # Reset state from any previous attempt
        self.ready = False
        self.stderr_lines = []
        self.stderr_callback = stderr_callback
        self.last_stderr_time = time.time()
        self.process = None
        while not self.response_queue.empty():
            try:
                self.response_queue.get_nowait()
            except queue.Empty:
                break

        cmd = [str(_exe), "gtp",
               "-model", str(_model),
               "-config", str(_cfg)]
        _ensure_user_katago_dirs()
        try:
            self.process = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, bufsize=0,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
        except OSError as e:
            raise RuntimeError(f"Failed to launch {_exe.name}: {e}") from e
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

        # Wait for stderr "GTP ready" signal (up to 120s for OpenCL first-time tuning)
        deadline = time.time() + startup_timeout
        found_ready = False
        last_progress_bucket = -1
        while time.time() < deadline:
            # Check if process crashed
            if self.process.poll() is not None:
                err = "\n".join(self.stderr_lines[-10:]) if self.stderr_lines else "no output"
                raise RuntimeError(
                    f"{Path(_exe).name} exited with code {self.process.returncode}: {err}")
            for line in self.stderr_lines:
                if "GTP ready" in line:
                    found_ready = True
                    break
            if found_ready:
                break
            if (
                stall_timeout > 0
                and self.last_stderr_time
                and time.time() - self.last_stderr_time > stall_timeout
            ):
                err = "\n".join(self.stderr_lines[-10:]) if self.stderr_lines else "no output"
                self.stop()
                raise RuntimeError(
                    f"{Path(_exe).name} stalled for {int(stall_timeout)}s without new output: {err}"
                )
            elapsed = int(startup_timeout - max(0.0, deadline - time.time()))
            progress_bucket = elapsed // 10
            if (
                self.stderr_callback
                and elapsed >= 10
                and progress_bucket > last_progress_bucket
            ):
                last_progress_bucket = progress_bucket
                self.stderr_callback(
                    f"{Path(_exe).name} 仍在初始化中，已等待 {elapsed}s"
                )
            time.sleep(0.3)

        if not found_ready:
            # Process still running but no GTP ready — kill and fail
            err = "\n".join(self.stderr_lines[-10:]) if self.stderr_lines else "no output"
            self.stop()
            raise RuntimeError(
                f"{Path(_exe).name} did not become ready within {int(startup_timeout)}s: {err}"
            )

        # Send a probe command to confirm GTP is responsive
        try:
            self.process.stdin.write(b"name\n")
            self.process.stdin.flush()
            resp = self.response_queue.get(timeout=10)
            self.ready = True
            log(f"[KataGo] Started: {resp}")
        except queue.Empty:
            log("[KataGo] Warning: no ready signal received, assuming OK")
            self.ready = True

    def _read_stdout(self):
        current_response = []
        for raw_line in self.process.stdout:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
            if self.is_analyzing and line.startswith("info "):
                with self.analysis_lock:
                    self.analysis_lines.append(line)
            elif self.is_analyzing and line.startswith("ownership "):
                vals = line.split()[1:]
                try:
                    with self.analysis_lock:
                        self.ownership_data = [float(v) for v in vals]
                except Exception:
                    pass
            else:
                if line.startswith("=") or line.startswith("?"):
                    current_response = [line]
                elif line == "" and current_response:
                    self.response_queue.put("\n".join(current_response))
                    current_response = []
                elif current_response:
                    current_response.append(line)

    def _read_stderr(self):
        for raw_line in self.process.stderr:
            line = raw_line.decode("utf-8", errors="replace").rstrip()
            if not line:
                continue
            self.last_stderr_time = time.time()
            self.stderr_lines.append(line)
            self.stderr_lines = self.stderr_lines[-200:]
            log(f"[KataGo stderr] {line}")
            if self.stderr_callback:
                try:
                    self.stderr_callback(line)
                except Exception:
                    pass

    def is_alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def _drain_response_queue(self, wait: float = 0.0) -> int:
        drained = 0
        deadline = time.time() + wait
        while True:
            timeout = max(0.0, deadline - time.time())
            try:
                if wait > 0 and time.time() < deadline:
                    self.response_queue.get(timeout=timeout)
                else:
                    self.response_queue.get_nowait()
                drained += 1
            except queue.Empty:
                break
        return drained

    def _send_command_locked(self, cmd: str, timeout: float = 60.0) -> str:
        if not self.process:
            return "? not started"
        if self.process.poll() is not None:
            log(f"[KataGo] Process dead (exit {self.process.poll()}), disabling engine")
            self.ready = False
            return "? process dead"
        try:
            with self.analysis_lock:
                self.is_analyzing = False
            self.process.stdin.write((cmd + "\n").encode())
            self.process.stdin.flush()
        except (OSError, ValueError, BrokenPipeError) as e:
            log(f"[KataGo] stdin write error: {e}, disabling engine")
            self.ready = False
            return "? write error"
        try:
            return self.response_queue.get(timeout=timeout)
        except queue.Empty:
            return "? timeout"

    def send_command(self, cmd: str, timeout: float = 60.0) -> str:
        with self.command_lock:
            return self._send_command_locked(cmd, timeout)

    def set_visits(self, visits: int):
        self.current_visits = visits
        max_visits = 10000000 if visits == 0 else visits
        self.send_command(f"kata-set-param maxVisits {max_visits}")

    def analyze(self, color: str, visits: int, interval: int = 50,
                duration: float = 1.8, extra_args: Optional[list[str]] = None) -> tuple:
        if not self.process or self.process.poll() is not None:
            return [], []

        with self.command_lock:
            original_visits = self.current_visits
            analysis_max_visits = 10000000 if visits == 0 else visits
            self._drain_response_queue(wait=0.05)

            if original_visits != visits:
                self.current_visits = visits
                resp = self._send_command_locked(
                    f"kata-set-param maxVisits {analysis_max_visits}",
                    timeout=10.0)
                if resp.startswith("?"):
                    log(f"[Analysis] set_visits failed: {resp}")

            with self.analysis_lock:
                self.analysis_lines = []
                self.ownership_data = []
                self.is_analyzing = True

            cmd_parts = ["kata-analyze", color, str(interval)]
            if extra_args:
                cmd_parts.extend(extra_args)
            cmd = " ".join(cmd_parts)
            log(f"[Analysis] sending: {cmd}")
            self.process.stdin.write((cmd + "\n").encode())
            self.process.stdin.flush()

            time.sleep(duration)

            try:
                self.process.stdin.write(b"stop\n")
                self.process.stdin.flush()
            except (OSError, ValueError, BrokenPipeError) as exc:
                log(f"[Analysis] stop failed: {exc}")

            time.sleep(0.25)
            with self.analysis_lock:
                self.is_analyzing = False
                lines = list(self.analysis_lines)
                ownership = list(self.ownership_data)

            drained = self._drain_response_queue(wait=0.4)
            if drained:
                log(f"[Analysis] drained {drained} sync responses")

            if original_visits != visits:
                self.current_visits = original_visits
                restore_max_visits = 10000000 if original_visits == 0 else original_visits
                restore_resp = self._send_command_locked(
                    f"kata-set-param maxVisits {restore_max_visits}",
                    timeout=10.0)
                if restore_resp.startswith("?"):
                    log(f"[Analysis] restore visits failed: {restore_resp}")

            log(f"[Analysis] collected {len(lines)} info lines, {len(ownership)} ownership vals")
            return lines, ownership

    def parse_analysis(self, lines: list, ownership: list,
                       size: int = 19, to_move_color: str = "B") -> dict:
        moves = []
        root_winrate = 0.5
        root_score = 0.0

        latest_line = ""
        for line in reversed(lines):
            if line.startswith("info "):
                latest_line = line
                break

        if not latest_line:
            return {
                "winrate": 0.5,
                "score": 0.0,
                "top_moves": [],
                "ownership": ownership,
                "analysis_color": to_move_color,
            }

        segments = [
            segment.strip()
            for segment in re.split(r"(?=info move )", latest_line)
            if segment.strip().startswith("info move ")
        ]

        for segment in segments:
            parts = segment.split()
            fields = {}
            i = 1
            while i < len(parts) - 1:
                key = parts[i]
                if key == "pv":
                    break
                fields[key] = parts[i + 1]
                i += 2

            move_gtp = fields.get("move")
            if not move_gtp:
                continue
            try:
                visits = int(fields.get("visits", 0))
                wr = float(fields.get("winrate", 0.5))
                score_mean = float(fields.get("scoreMean", 0.0))
                order = int(fields.get("order", 999))
            except (ValueError, TypeError):
                log(f"[Analysis] parse error for segment: {segment[:120]}")
                continue

            if order == 0:
                root_winrate = wr
                root_score = score_mean
            if move_gtp.upper() != "PASS":
                coord = gtp_to_coord(move_gtp, size)
                if coord:
                    moves.append({
                        "x": coord[0], "y": coord[1],
                        "winrate": round(wr, 3),
                        "black_winrate": round(wr if to_move_color == "B" else 1.0 - wr, 3),
                        "visits": visits,
                        "gtp": move_gtp,
                        "order": order,
                    })

        root_match = re.search(r"\brootInfo\b(.*?)(?=\bownership\b|\bownershipStdev\b|$)", latest_line)
        if root_match:
            root_fields = {}
            root_parts = root_match.group(1).split()
            i = 0
            while i < len(root_parts) - 1:
                root_fields[root_parts[i]] = root_parts[i + 1]
                i += 2
            try:
                root_winrate = float(root_fields.get("winrate", root_winrate))
                root_score = float(root_fields.get("scoreLead", root_fields.get("scoreMean", root_score)))
            except (TypeError, ValueError):
                pass

        if not ownership:
            ownership_match = re.search(r"\bownership\b(.*?)(?=\bownershipStdev\b|$)", latest_line)
            if ownership_match:
                vals = ownership_match.group(1).split()
                expected = size * size
                try:
                    ownership = [float(v) for v in vals[:expected]]
                except ValueError:
                    ownership = []

        if ownership and to_move_color == "W":
            ownership = [-v for v in ownership]

        moves.sort(key=lambda m: m["order"])
        black_winrate = root_winrate if to_move_color == "B" else 1.0 - root_winrate
        black_score = root_score if to_move_color == "B" else -root_score
        return {
            "winrate": round(black_winrate, 3),
            "score": round(black_score, 1),
            "top_moves": moves[:8],
            "ownership": ownership,   # flat list, len = size*size
            "analysis_color": to_move_color,
        }

    def stop(self):
        if self.process:
            try:
                self.send_command("quit", timeout=3)
            except Exception:
                pass
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
        self.ready = False
        self.stderr_callback = None

    def restart(self):
        """Stop and re-start the engine."""
        self.stop()
        time.sleep(0.5)
        self.start()


# ─── Game state ──────────────────────────────────────────────────────────────
class GoGame:
    def __init__(self, size: int = 19, komi: float = 7.5, handicap: int = 0,
                 player_color: str = "B", level: str = "a3d",
                 two_player: bool = False):
        self.size = size
        self.komi = komi
        self.handicap = handicap
        self.player_color = player_color
        self.ai_color = "W" if player_color == "B" else "B"
        self.level = level
        self.two_player = two_player
        self.moves = []
        self.current_player = "B"
        self.board = [[0] * size for _ in range(size)]
        self.captures = {"B": 0, "W": 0}
        self.game_over = False
        self.winner = None
        self.passed = {"B": False, "W": False}
        self.territory = None
        # Rogue mode
        self.rogue_enabled: bool = False
        self.rogue_card: Optional[str] = None
        self.rogue_uses: dict[str, int] = {}     # card_id → remaining uses
        self.rogue_seal_points: list[tuple] = []  # forbidden (x,y) for AI
        self.rogue_waiting_seal: bool = False      # waiting for seal point input
        self.rogue_skip_ai: bool = False           # twin star: skip next AI turn
        self.ai_rogue_enabled: bool = False
        self.ai_rogue_card: Optional[str] = None
        self.ai_rogue_seal_points: list[tuple] = []
        # 定式强迫症: 8 random target points, player must hit 3 of them
        self.rogue_joseki_targets: list[tuple] = []
        self.rogue_joseki_hits: int = 0
        self.rogue_joseki_done: bool = False
        self.rogue_godhand_center: Optional[tuple[int, int]] = None
        self.rogue_godhand_trigger: list[tuple] = []
        self.rogue_godhand_done: bool = False
        self.rogue_sansan_trap_done: bool = False
        self.ai_rogue_sansan_trap_done: bool = False
        self.rogue_corner_helper_done: bool = False
        self.rogue_sanrensei_done: bool = False
        self.rogue_quickthink_stage: int = 0
        self.rogue_fool_shapes: set[tuple[tuple[int, int], ...]] = set()
        # 让子棋任务: player passes 2 turns, then gets bonus turns
        self.rogue_handicap_passes: int = 0       # passes completed (need 2)
        self.rogue_handicap_active: bool = False   # task completed, bonus active
        self.rogue_handicap_bonuses: int = 0       # bonus turns used (max 3)
        # Ultimate rogue mode (大招模式)
        self.ultimate: bool = False
        self.ultimate_player_card: Optional[str] = None
        self.ultimate_ai_card: Optional[str] = None
        self.ultimate_move_count: int = 0          # total moves (both sides)
        self.ultimate_extra_turn: bool = False     # chain/double: extra turn flag
        self.ultimate_double_pending: bool = False # double: waiting for 2nd stone
        self.ultimate_territory_pts: list[tuple] = []  # cached forbidden points
        self.ultimate_joseki_targets: list[tuple] = []
        self.ultimate_joseki_hits: int = 0
        self.ultimate_joseki_done: bool = False
        self.ultimate_godhand_center: Optional[tuple[int, int]] = None
        self.ultimate_godhand_trigger: list[tuple] = []
        self.ultimate_godhand_done: bool = False
        self.ultimate_corner_helper_done: bool = False
        self.ultimate_sanrensei_done: bool = False
        self.ultimate_quickthink_active: bool = False
        self.ultimate_quickthink_token: int = 0
        self.ultimate_fool_shapes: set[tuple[tuple[int, int], ...]] = set()

    # ─── Board logic ─────────────────────────────────────────────────────────
    def neighbors(self, x, y):
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.size and 0 <= ny < self.size:
                yield nx, ny

    def get_group(self, x, y):
        color = self.board[y][x]
        if color == 0:
            return set()
        group, stack = set(), [(x, y)]
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in group:
                continue
            group.add((cx, cy))
            for nx, ny in self.neighbors(cx, cy):
                if self.board[ny][nx] == color and (nx, ny) not in group:
                    stack.append((nx, ny))
        return group

    def has_liberty(self, group):
        for x, y in group:
            for nx, ny in self.neighbors(x, y):
                if self.board[ny][nx] == 0:
                    return True
        return False

    def place_stone(self, x, y, color):
        cv = 1 if color == "B" else 2
        ov = 3 - cv
        self.board[y][x] = cv
        captured = 0
        for nx, ny in self.neighbors(x, y):
            if self.board[ny][nx] == ov:
                grp = self.get_group(nx, ny)
                if not self.has_liberty(grp):
                    for gx, gy in grp:
                        self.board[gy][gx] = 0
                    captured += len(grp)
        self.captures[color] = self.captures.get(color, 0) + captured
        return captured

    def rebuild_board(self):
        self.board = [[0] * self.size for _ in range(self.size)]
        self.captures = {"B": 0, "W": 0}
        for color, gtp in self.moves:
            if gtp.upper() == "PASS":
                continue
            coord = gtp_to_coord(gtp, self.size)
            if coord:
                self.place_stone(coord[0], coord[1], color)

    def to_state(self) -> dict:
        return {
            "board": self.board,
            "size": self.size,
            "komi": self.komi,
            "handicap": self.handicap,
            "current_player": self.current_player,
            "player_color": self.player_color,
            "ai_color": self.ai_color,
            "captures": self.captures,
            "move_number": len(self.moves),
            "game_over": self.game_over,
            "winner": self.winner,
            "last_move": self.moves[-1] if self.moves else None,
            "moves_list": [[c, g] for c, g in self.moves],
            "level": self.level,
            "two_player": self.two_player,
            "rogue_enabled": self.rogue_enabled,
            "rogue_card": self.rogue_card,
            "rogue_uses": self.rogue_uses,
            "rogue_seal_points": [[x, y] for x, y in self.rogue_seal_points],
            "ai_rogue_enabled": self.ai_rogue_enabled,
            "ai_rogue_card": self.ai_rogue_card,
            "ai_rogue_seal_points": [[x, y] for x, y in self.ai_rogue_seal_points],
            "rogue_joseki_targets": [[x, y] for x, y in self.rogue_joseki_targets],
            "rogue_joseki_done": self.rogue_joseki_done,
            "rogue_undo_disabled": self.rogue_card == "no_regret",
            "rogue_quickthink_stage": self.rogue_quickthink_stage,
            "rogue_quickthink_seconds": (
                ROGUE_QUICKTHINK_FIRST_SECONDS
                if self.rogue_quickthink_stage == 1
                else ROGUE_QUICKTHINK_SECOND_SECONDS
                if self.rogue_quickthink_stage == 2
                else 0
            ),
            "rogue_handicap_active": self.rogue_handicap_active,
            "rogue_handicap_passes": self.rogue_handicap_passes,
            "ultimate": self.ultimate,
            "ultimate_player_card": self.ultimate_player_card,
            "ultimate_ai_card": self.ultimate_ai_card,
            "ultimate_move_count": self.ultimate_move_count,
            "ultimate_max_moves": 20,
            "ultimate_extra_turn": self.ultimate_extra_turn,
            "ultimate_double_pending": self.ultimate_double_pending,
            "ultimate_joseki_targets": [[x, y] for x, y in self.ultimate_joseki_targets],
            "ultimate_joseki_hits": self.ultimate_joseki_hits,
            "ultimate_joseki_done": self.ultimate_joseki_done,
            "ultimate_quickthink_active": self.ultimate_quickthink_active,
            "ultimate_quickthink_token": self.ultimate_quickthink_token,
            "ultimate_quickthink_seconds": (
                ULTIMATE_QUICKTHINK_SECONDS if self.ultimate_quickthink_active else 0
            ),
        }


def gtp_to_sgf(gtp_move: str, size: int = 19) -> str:
    """Convert GTP coordinate (e.g. 'D4') to SGF coordinate (e.g. 'dd')."""
    if gtp_move.upper() == "PASS":
        return ""
    cols = "ABCDEFGHJKLMNOPQRST"
    try:
        col = cols.index(gtp_move[0].upper())
        row = size - int(gtp_move[1:])
        return chr(ord('a') + col) + chr(ord('a') + row)
    except (ValueError, IndexError):
        return ""


def generate_sgf(game: GoGame) -> str:
    """Generate SGF string from a GoGame."""
    import datetime
    dt = datetime.date.today().isoformat()
    header = (f"(;GM[1]FF[4]CA[UTF-8]AP[GoAI:1.0]"
              f"SZ[{game.size}]KM[{game.komi}]"
              f"DT[{dt}]PB[{('Player' if game.player_color == 'B' else 'AI')}]"
              f"PW[{('Player' if game.player_color == 'W' else 'AI')}]"
              f"RE[{('B' if game.winner == 'B' else 'W') + '+' if game.winner else '?'}]")
    if game.handicap > 0:
        header += f"HA[{game.handicap}]"
    header += "\n"
    body = ""
    for color, gtp in game.moves:
        sgf_coord = gtp_to_sgf(gtp, game.size)
        prop = "B" if color == "B" else "W"
        body += f";{prop}[{sgf_coord}]\n"
    return header + body + ")\n"


# ─── FastAPI App ─────────────────────────────────────────────────────────────
app = FastAPI()
engine = KataGoEngine()
active_games: dict[str, GoGame] = {}
ENGINE_STATE_LOCK = threading.Lock()
ENGINE_START_THREAD: Optional[threading.Thread] = None
ENGINE_START_TOKEN = 0
ENGINE_EVENT_LOG = deque(maxlen=120)
ENGINE_STATE = {
    "phase": "disabled" if NO_KATAGO else "idle",
    "message": "KataGo disabled" if NO_KATAGO else "KataGo not started yet",
    "active_backend": None,
    "active_backend_exe": None,
    "active_model": None,
    "last_error": None,
    "attempts": [],
    "candidates": [],
    "nvidia_detected": False,
    "updated_at": time.time(),
}


def _engine_log(message: str):
    stamped = f"[Engine] {message}"
    with ENGINE_STATE_LOCK:
        ENGINE_EVENT_LOG.append({
            "ts": time.strftime("%H:%M:%S"),
            "message": stamped,
        })
    log(stamped)


def _set_engine_state(**changes):
    with ENGINE_STATE_LOCK:
        ENGINE_STATE.update(changes)
        ENGINE_STATE["updated_at"] = time.time()


def _engine_state_snapshot() -> dict:
    with ENGINE_STATE_LOCK:
        snapshot = dict(ENGINE_STATE)
        snapshot["attempts"] = [dict(item) for item in ENGINE_STATE.get("attempts", [])]
        snapshot["candidates"] = list(ENGINE_STATE.get("candidates", []))
        snapshot["log_tail"] = [dict(item) for item in ENGINE_EVENT_LOG]
        snapshot["initializing"] = snapshot.get("phase") == "initializing"
        snapshot["ready"] = snapshot.get("phase") == "ready"
        return snapshot


def _next_engine_token() -> int:
    global ENGINE_START_TOKEN
    with ENGINE_STATE_LOCK:
        ENGINE_START_TOKEN += 1
        return ENGINE_START_TOKEN


def _engine_token_is_current(token: int) -> bool:
    with ENGINE_STATE_LOCK:
        return token == ENGINE_START_TOKEN


def _select_model() -> Optional[Path]:
    for candidate in (USER_KATAGO_MODEL_LARGE, KATAGO_MODEL_LARGE, KATAGO_MODEL, KATAGO_MODEL_SMALL):
        if candidate.exists():
            return candidate
    return None


def _build_engine_candidates() -> tuple[bool, list[dict]]:
    has_gpu = _has_nvidia_gpu()
    candidates = []
    if has_gpu and KATAGO_CUDA_EXE.exists():
        candidates.append({
            "exe": KATAGO_CUDA_EXE,
            "config": KATAGO_CONFIG,
            "cpu_mode": False,
            "label": "CUDA(升级包)",
        })
    if has_gpu and KATAGO_EXE.exists():
        candidates.append({
            "exe": KATAGO_EXE,
            "config": KATAGO_CONFIG,
            "cpu_mode": False,
            "label": "CUDA",
        })
    if KATAGO_OPENCL_EXE.exists():
        candidates.append({
            "exe": KATAGO_OPENCL_EXE,
            "config": KATAGO_CONFIG,
            "cpu_mode": False,
            "label": "OpenCL",
        })
    if KATAGO_CPU_EXE.exists():
        candidates.append({
            "exe": KATAGO_CPU_EXE,
            "config": KATAGO_CPU_CONFIG if KATAGO_CPU_CONFIG.exists() else KATAGO_CONFIG,
            "cpu_mode": True,
            "label": "CPU",
        })
    return has_gpu, candidates


def _build_engine_candidates() -> tuple[bool, list[dict]]:
    has_gpu = _has_nvidia_gpu()
    candidates = []
    if has_gpu and USER_KATAGO_CUDA_EXE.exists():
        candidates.append({
            "exe": USER_KATAGO_CUDA_EXE,
            "config": KATAGO_CONFIG,
            "cpu_mode": False,
            "label": "CUDA(升级包)",
            "startup_timeout": 60.0,
            "stall_timeout": 20.0,
        })
    if has_gpu and KATAGO_CUDA_EXE.exists():
        candidates.append({
            "exe": KATAGO_CUDA_EXE,
            "config": KATAGO_CONFIG,
            "cpu_mode": False,
            "label": "CUDA(随包)",
            "startup_timeout": 60.0,
            "stall_timeout": 20.0,
        })
    if has_gpu and KATAGO_EXE.exists():
        candidates.append({
            "exe": KATAGO_EXE,
            "config": KATAGO_CONFIG,
            "cpu_mode": False,
            "label": "CUDA",
            "startup_timeout": 60.0,
            "stall_timeout": 20.0,
        })
    if KATAGO_OPENCL_EXE.exists():
        candidates.append({
            "exe": KATAGO_OPENCL_EXE,
            "config": KATAGO_CONFIG,
            "cpu_mode": False,
            "label": "OpenCL",
            "startup_timeout": 150.0,
            "stall_timeout": 45.0,
        })
    if KATAGO_CPU_EXE.exists():
        candidates.append({
            "exe": KATAGO_CPU_EXE,
            "config": KATAGO_CPU_CONFIG if KATAGO_CPU_CONFIG.exists() else KATAGO_CONFIG,
            "cpu_mode": True,
            "label": "CPU",
            "startup_timeout": 45.0,
            "stall_timeout": 20.0,
        })
    return has_gpu, candidates


def _select_model() -> Optional[Path]:
    for candidate in (KATAGO_MODEL_LARGE, KATAGO_MODEL, KATAGO_MODEL_SMALL):
        if candidate.exists():
            return candidate
    return None


def _build_engine_candidates() -> tuple[bool, list[dict]]:
    has_gpu = _has_nvidia_gpu()
    candidates = []
    if has_gpu and KATAGO_CUDA_EXE.exists():
        candidates.append({
            "exe": KATAGO_CUDA_EXE,
            "config": KATAGO_CONFIG,
            "cpu_mode": False,
            "label": "CUDA(升级包)",
            "startup_timeout": 60.0,
            "stall_timeout": 20.0,
        })
    if has_gpu and KATAGO_EXE.exists():
        candidates.append({
            "exe": KATAGO_EXE,
            "config": KATAGO_CONFIG,
            "cpu_mode": False,
            "label": "CUDA",
            "startup_timeout": 60.0,
            "stall_timeout": 20.0,
        })
    if KATAGO_OPENCL_EXE.exists():
        candidates.append({
            "exe": KATAGO_OPENCL_EXE,
            "config": KATAGO_CONFIG,
            "cpu_mode": False,
            "label": "OpenCL",
            "startup_timeout": 150.0,
            "stall_timeout": 45.0,
        })
    if KATAGO_CPU_EXE.exists():
        candidates.append({
            "exe": KATAGO_CPU_EXE,
            "config": KATAGO_CPU_CONFIG if KATAGO_CPU_CONFIG.exists() else KATAGO_CONFIG,
            "cpu_mode": True,
            "label": "CPU",
            "startup_timeout": 45.0,
            "stall_timeout": 20.0,
        })
    return has_gpu, candidates


def _engine_progress_callback(label: str, token: int, line: str):
    if not _engine_token_is_current(token):
        return
    lower_line = line.lower()
    if "gtp ready" in lower_line:
        _set_engine_state(message=f"{label} 引擎已返回 GTP ready")
        return
    if "opencl" in lower_line or "tuning" in lower_line:
        _set_engine_state(message=f"{label} 初始化中: {line[:180]}")
        return
    if "cuda" in lower_line or "cudnn" in lower_line:
        _set_engine_state(message=f"{label} 初始化中: {line[:180]}")
        return


def _run_engine_startup(trigger: str, token: int):
    global CPU_MODE, ENGINE_START_THREAD
    try:
        if NO_KATAGO:
            _set_engine_state(
                phase="disabled",
                message="KataGo disabled by --no-katago",
                active_backend=None,
                active_backend_exe=None,
                active_model=None,
                last_error=None,
                attempts=[],
                candidates=[],
                nvidia_detected=False,
            )
            _engine_log(f"{trigger}: KataGo disabled, skip startup")
            return

        model = _select_model()
        if not model:
            CPU_MODE = False
            _set_engine_state(
                phase="failed",
                message="未找到 KataGo 模型，当前仅支持纯对弈",
                active_backend=None,
                active_backend_exe=None,
                active_model=None,
                last_error="No KataGo model found",
                attempts=[],
                candidates=[],
                nvidia_detected=False,
            )
            _engine_log(f"{trigger}: no model found")
            return

        has_gpu, candidates = _build_engine_candidates()
        if not candidates:
            CPU_MODE = False
            _set_engine_state(
                phase="failed",
                message="未找到任何 KataGo 引擎，当前仅支持纯对弈",
                active_backend=None,
                active_backend_exe=None,
                active_model=model.name,
                last_error="No KataGo engine found",
                attempts=[],
                candidates=[],
                nvidia_detected=has_gpu,
            )
            _engine_log(f"{trigger}: no engine found")
            return

        attempts = []
        _set_engine_state(
            phase="initializing",
            message=f"正在准备模型 {model.name}",
            active_backend=None,
            active_backend_exe=None,
            active_model=model.name,
            last_error=None,
            attempts=attempts,
            candidates=[item["label"] for item in candidates],
            nvidia_detected=has_gpu,
        )
        _engine_log(f"{trigger}: selected model {model.name}")

        for idx, candidate in enumerate(candidates, start=1):
            if not _engine_token_is_current(token):
                _engine_log(f"{trigger}: startup cancelled before {candidate['label']}")
                return

            exe = candidate["exe"]
            cfg = candidate["config"]
            is_cpu = candidate["cpu_mode"]
            label = candidate["label"]
            attempt = {
                "label": label,
                "exe": exe.name,
                "config": cfg.name,
                "status": "starting",
            }
            attempts.append(attempt)
            _set_engine_state(
                phase="initializing",
                message=f"尝试启动 {label} 引擎 ({idx}/{len(candidates)})",
                active_backend=label,
                active_backend_exe=exe.name,
                active_model=model.name,
                last_error=None,
                attempts=attempts,
                nvidia_detected=has_gpu,
            )
            _engine_log(f"Trying {label}: {exe.name} with {model.name}")
            try:
                engine.start(
                    exe,
                    cfg,
                    model,
                    startup_timeout=float(candidate.get("startup_timeout", 120.0)),
                    stall_timeout=float(candidate.get("stall_timeout", 45.0)),
                    stderr_callback=lambda line, current_label=label: _engine_progress_callback(
                        current_label, token, line
                    ),
                )
                if not _engine_token_is_current(token):
                    engine.stop()
                    _engine_log(f"{trigger}: startup cancelled after {label} became ready")
                    return
                attempt["status"] = "ready"
                CPU_MODE = is_cpu
                _set_engine_state(
                    phase="ready",
                    message=f"{label} 引擎已就绪",
                    active_backend=label,
                    active_backend_exe=exe.name,
                    active_model=model.name,
                    last_error=None,
                    attempts=attempts,
                    nvidia_detected=has_gpu,
                )
                _engine_log(f"{label} ready with model {model.name}")
                return
            except Exception as exc:
                attempt["status"] = "failed"
                attempt["error"] = str(exc)
                CPU_MODE = False
                _engine_log(f"{label} failed: {exc}")
                engine.stop()
                if not _engine_token_is_current(token):
                    _engine_log(f"{trigger}: startup cancelled after {label} failure")
                    return
                has_more = idx < len(candidates)
                _set_engine_state(
                    phase="initializing" if has_more else "failed",
                    message=(
                        f"{label} 启动失败，正在尝试下一个后端"
                        if has_more else
                        "所有引擎启动失败，当前仅支持纯对弈"
                    ),
                    active_backend=label,
                    active_backend_exe=exe.name,
                    active_model=model.name,
                    last_error=str(exc),
                    attempts=attempts,
                    nvidia_detected=has_gpu,
                )

        CPU_MODE = False
        _set_engine_state(
            phase="failed",
            message="所有引擎启动失败，当前仅支持纯对弈",
            last_error=ENGINE_STATE.get("last_error"),
            attempts=attempts,
            nvidia_detected=has_gpu,
        )
    finally:
        with ENGINE_STATE_LOCK:
            if ENGINE_START_THREAD is threading.current_thread():
                ENGINE_START_THREAD = None


def _start_engine_background(trigger: str, force_restart: bool = False) -> tuple[bool, str]:
    global ENGINE_START_THREAD, CPU_MODE
    if force_restart:
        CPU_MODE = False
        engine.stop()

    with ENGINE_STATE_LOCK:
        if ENGINE_START_THREAD and ENGINE_START_THREAD.is_alive():
            return False, "KataGo is already initializing"

    token = _next_engine_token()
    thread = threading.Thread(
        target=_run_engine_startup,
        args=(trigger, token),
        daemon=True,
    )
    with ENGINE_STATE_LOCK:
        ENGINE_START_THREAD = thread
    thread.start()
    return True, "started"


def _has_nvidia_gpu() -> bool:
    """Check if an NVIDIA GPU is available via nvidia-smi."""
    try:
        subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            timeout=10,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        return True
    except Exception:
        return False


@app.on_event("startup")
async def startup():
    if NO_KATAGO:
        log("[Server] KataGo disabled (--no-katago). Free-play mode.")
        return

    started, reason = _start_engine_background("startup")
    if started:
        log("[Server] KataGo initialization scheduled in background")
    else:
        log(f"[Server] KataGo background init skipped: {reason}")


@app.on_event("shutdown")
async def shutdown():
    engine.stop()


app.mount("/static", StaticFiles(directory=str(STATIC_DIR), check_dir=False),
          name="static")


@app.middleware("http")
async def no_cache_html(request: Request, call_next):
    response = await call_next(request)
    # Prevent browser from caching HTML / API responses
    if "text/html" in response.headers.get("content-type", ""):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/")
async def root():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return Response(
            content="static/index.html not found",
            media_type="text/plain; charset=utf-8",
            status_code=500,
        )
    return FileResponse(str(index_path))


@app.get("/ranks")
async def get_ranks():
    return [{"id": k, "label": v} for k, v in RANK_LABELS.items()]


@app.post("/stop_katago")
async def stop_katago():
    """Stop the KataGo engine while keeping the server running."""
    snapshot = _engine_state_snapshot()
    if snapshot.get("phase") not in {"ready", "initializing"} and not engine.ready:
        return {"ok": False, "error": "KataGo is not running"}
    try:
        _next_engine_token()
        await run_in_executor(engine.stop)
        _set_engine_state(
            phase="stopped",
            message="KataGo 已停止，当前为纯对弈模式",
            active_backend=None,
            active_backend_exe=None,
            last_error=None,
        )
        log("[Server] KataGo engine stopped via API")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/restart_katago")
async def restart_katago():
    """Restart the KataGo engine."""
    if NO_KATAGO:
        return {"ok": False, "error": "KataGo is disabled (--no-katago)"}
    model = _select_model()
    _, candidates = _build_engine_candidates()
    if not model:
        return {"ok": False, "error": "KataGo model not found"}
    if not candidates:
        return {"ok": False, "error": "KataGo engine not found"}
    started, reason = _start_engine_background("api_restart", force_restart=True)
    snapshot = _engine_state_snapshot()
    if started:
        log("[Server] KataGo restart scheduled in background")
        return {
            "ok": True,
            "phase": snapshot.get("phase"),
            "message": snapshot.get("message"),
        }
    return {
        "ok": False,
        "error": reason,
        "phase": snapshot.get("phase"),
        "message": snapshot.get("message"),
    }


@app.get("/status")
async def get_status():
    snapshot = _engine_state_snapshot()
    model_exists = any(path.exists() for path in (
        KATAGO_MODEL_LARGE, KATAGO_MODEL, KATAGO_MODEL_SMALL,
    ))
    exe_exists = any(path.exists() for path in (
        KATAGO_CUDA_EXE, KATAGO_EXE, KATAGO_OPENCL_EXE, KATAGO_CPU_EXE,
    ))
    return {
        "server_rev": SERVER_REV,
        "host": SERVER_HOST,
        "port": SERVER_PORT,
        "access_urls": get_access_urls(SERVER_PORT),
        "katago_ready": engine.ready,
        "katago_exe": exe_exists,
        "katago_model": model_exists,
        "no_katago": NO_KATAGO,
        "cpu_mode": CPU_MODE,
        "static_ready": (STATIC_DIR / "index.html").exists(),
        "engine_phase": snapshot.get("phase"),
        "engine_message": snapshot.get("message"),
        "engine_backend": snapshot.get("active_backend"),
        "engine_backend_exe": snapshot.get("active_backend_exe"),
        "engine_model": snapshot.get("active_model"),
        "engine_last_error": snapshot.get("last_error"),
        "engine_attempts": snapshot.get("attempts"),
        "engine_candidates": snapshot.get("candidates"),
        "engine_initializing": snapshot.get("initializing"),
        "engine_log_tail": snapshot.get("log_tail"),
        "nvidia_detected": snapshot.get("nvidia_detected"),
    }


# ─── GPU detection ───────────────────────────────────────────────────────────
# GPU tier mapping: determines default rank and slow-rank threshold
# Tier 4 (high-end): RTX 3080+, 4070+, 5070+ → default a5d, slow at p1d
# Tier 3 (mid):      RTX 2060-3070, GTX 1080Ti → default a3d, slow at a6d
# Tier 2 (low):      GTX 1060-1070 → default a1d, slow at a3d
# Tier 1 (very low): GT 1030, integrated, unknown → default 3k, slow at 1k

_GPU_TIERS = {
    # tier: (default_rank, slow_from_rank, label)
    4: ("a5d", "p1d", "高端"),
    3: ("a3d", "a6d", "中端"),
    2: ("a1d", "a3d", "入门"),
    1: ("3k",  "1k",  "低端"),
}

_GPU_TIER_PATTERNS = [
    # (regex_pattern, tier) — matched against GPU name, first match wins
    (r"RTX\s*50[789]0|RTX\s*5090|RTX\s*4090|RTX\s*4080|RTX\s*3090|A100|H100|A6000", 4),
    (r"RTX\s*40[67]0|RTX\s*3080|RTX\s*3070|RTX\s*2080|RTX\s*2070|GTX\s*1080\s*Ti|RTX\s*A[45]000", 4),
    (r"RTX\s*4060|RTX\s*4050|RTX\s*3060|RTX\s*3050|RTX\s*2060|RTX\s*2050|GTX\s*1080(?!\s*Ti)", 3),
    (r"GTX\s*1070|GTX\s*1660|GTX\s*1650|RTX\s*A2000", 3),
    (r"GTX\s*1060|GTX\s*1050|GTX\s*980|GTX\s*970|GTX\s*960|MX\s*[345]\d0", 2),
    (r"GTX\s*950|GTX\s*750|GT\s*1030|GT\s*730|GT\s*710|MX\s*[12]\d0", 1),
]

_gpu_cache: dict = {}


def _detect_gpu() -> dict:
    """Detect NVIDIA GPU using nvidia-smi. Returns gpu info dict."""
    if _gpu_cache:
        return _gpu_cache

    result = {"name": "Unknown", "vram_mb": 0, "tier": 1,
              "default_rank": "3k", "slow_from": "1k", "tier_label": "未知"}
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total",
             "--format=csv,noheader,nounits"],
            timeout=10, creationflags=0x08000000  # CREATE_NO_WINDOW
        ).decode("utf-8", errors="replace").strip()
        if out:
            parts = out.split("\n")[0].split(",")
            gpu_name = parts[0].strip()
            vram = int(float(parts[1].strip())) if len(parts) > 1 else 0
            result["name"] = gpu_name
            result["vram_mb"] = vram

            # Match GPU tier
            tier = 1
            for pattern, t in _GPU_TIER_PATTERNS:
                if re.search(pattern, gpu_name, re.IGNORECASE):
                    tier = t
                    break
            else:
                # Fallback: use VRAM as rough tier indicator
                if vram >= 10000:
                    tier = 4
                elif vram >= 6000:
                    tier = 3
                elif vram >= 3000:
                    tier = 2

            result["tier"] = tier
            info = _GPU_TIERS[tier]
            result["default_rank"] = info[0]
            result["slow_from"] = info[1]
            result["tier_label"] = info[2]
    except Exception:
        pass

    _gpu_cache.update(result)
    return result


# Rank ordering for slow-from comparison
_RANK_ORDER = list(RANK_VISITS.keys())


@app.get("/gpu")
async def get_gpu_info():
    info = await run_in_executor(_detect_gpu)
    info["cpu_mode"] = CPU_MODE
    info["large_model"] = KATAGO_MODEL_LARGE.exists()
    if CPU_MODE:
        info["default_rank"] = "5k"
        info["slow_from"] = "1k"
        info["tier_label"] = "CPU模式"
    return info


@app.get("/sgf/{game_id}")
async def export_sgf(game_id: str):
    game = active_games.get(game_id)
    if not game:
        return Response(content="Game not found", status_code=404)
    sgf = generate_sgf(game)
    return Response(
        content=sgf,
        media_type="application/x-go-sgf",
        headers={"Content-Disposition": f'attachment; filename="goai_{game_id}.sgf"'},
    )


async def run_in_executor(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    await websocket.accept()

    # Restore existing game if this gameId is already known
    game: Optional[GoGame] = active_games.get(game_id)

    async def send(data: dict):
        await websocket.send_text(json.dumps(data))

    async def send_error(msg: str):
        await send({"type": "error", "message": msg})

    async def do_analysis(g: GoGame) -> dict:
        if not engine.ready:
            return {"winrate": 0.5, "score": 0.0, "top_moves": [],
                    "ownership": []}
        color = g.current_player
        analysis_visits = max(80, min(get_game_visits(g.level, len(g.moves)) // 2, 1000))

        def _analyze():
            try:
                lines, ownership = engine.analyze(
                    color,
                    visits=analysis_visits,
                    interval=50,
                    duration=1.0,
                    extra_args=["rootInfo", "true", "ownership", "true"],
                )
                result = engine.parse_analysis(
                    lines,
                    ownership,
                    g.size,
                    to_move_color=color,
                )
                print(f"[Analysis] top_moves={len(result.get('top_moves',[]))} winrate={result.get('winrate')}")
                return result
            except Exception as ex:
                import traceback
                print(f"[Analysis] error: {ex}")
                traceback.print_exc()
                return {"winrate": 0.5, "score": 0.0, "top_moves": [],
                        "ownership": []}

        return await run_in_executor(_analyze)

    async def do_analysis_bg(g: GoGame):
        """Run analysis in background so the AI move is shown immediately."""
        try:
            move_count_before = len(g.moves)
            result = await do_analysis(g)
            # Skip sending if game state changed during analysis (stale)
            if g.game_over or len(g.moves) != move_count_before:
                return
            await send({"type": "analysis", **result})
        except Exception as ex:
            print(f"[Analysis-bg] error: {ex}")

    try:
        while True:
            data = json.loads(await websocket.receive_text())
            action = data.get("action")
            try:
                # ── reconnect ────────────────────────────────────────────────
                if action == "reconnect":
                    saved = active_games.get(game_id)
                    if saved:
                        game = saved
                        await send({"type": "reconnected", **game.to_state()})
                        if not game.game_over and engine.ready:
                            analysis = await do_analysis(game)
                            await send({"type": "analysis", **analysis})
                    else:
                        await send({"type": "reconnect_failed"})

                # ── new_game ──────────────────────────────────────────────────
                elif action == "new_game":
                    if not engine.ready and not data.get("two_player", False):
                        snapshot = _engine_state_snapshot()
                        await send({
                            "type": "engine_not_ready",
                            "phase": snapshot.get("phase"),
                            "message": snapshot.get("message"),
                            "last_error": snapshot.get("last_error"),
                            "log_tail": snapshot.get("log_tail"),
                        })
                        await send_error(
                            snapshot.get("message")
                            or "KataGo未就绪，请稍候重试，或先使用两人对局模式"
                        )
                        continue

                    size = int(data.get("size", 19))
                    komi = float(data.get("komi", 7.5))
                    handicap = int(data.get("handicap", 0))
                    player_color = data.get("player_color", "B")
                    level = data.get("level", "a3d")
                    two_player = bool(data.get("two_player", False))
                    rogue_enabled = bool(data.get("rogue", False))
                    ai_rogue_enabled = bool(data.get("ai_rogue", False)) and rogue_enabled and not two_player

                    game = GoGame(size, komi, handicap, player_color, level,
                                  two_player)
                    game.rogue_enabled = rogue_enabled
                    game.ai_rogue_enabled = ai_rogue_enabled
                    active_games[game_id] = game

                    if engine.ready:
                        visits = get_game_visits(level, len(game.moves))
                        await run_in_executor(engine.set_visits, visits)
                        await run_in_executor(engine.send_command,
                                             f"boardsize {size}")
                        await run_in_executor(engine.send_command, "clear_board")
                        await run_in_executor(engine.send_command, f"komi {komi}")
                        # Set rules based on komi: Chinese for 7.5, Japanese for 6.5
                        rules = "chinese" if komi == 7.5 else "japanese"
                        await run_in_executor(engine.send_command,
                                             f"kata-set-rules {rules}")

                    if handicap > 0 and engine.ready:
                        resp = await run_in_executor(
                            engine.send_command, f"fixed_handicap {handicap}")
                        if resp.startswith("="):
                            for gtp in resp[1:].strip().split():
                                coord = gtp_to_coord(gtp, size)
                                if coord:
                                    game.place_stone(coord[0], coord[1], "B")
                                    game.moves.append(("B", gtp))
                            game.current_player = "W"

                    await send({"type": "game_start", **game.to_state()})

                    # ── Ultimate Rogue mode: both sides pick cards ────
                    ultimate = bool(data.get("ultimate", False))
                    if ultimate and not two_player and engine.ready:
                        game.ultimate = True
                        choices = pick_ultimate_choices(3)
                        cards_data = []
                        for cid in choices:
                            c = ULTIMATE_CARDS[cid]
                            cards_data.append({
                                "id": cid, "name": c["name"],
                                "desc": c["desc"], "icon": c["icon"],
                            })
                        await send({"type": "ultimate_offer",
                                    "cards": cards_data})
                        # Game waits for player card selection

                    # ── Rogue mode: offer 3 cards before game starts ─────
                    elif rogue_enabled and (two_player or engine.ready):
                        rogue_pool = TWO_PLAYER_ROGUE_POOL if two_player else None
                        choices = pick_rogue_choices(3, pool=rogue_pool)
                        cards_data = []
                        for cid in choices:
                            c = ROGUE_CARDS[cid]
                            cards_data.append({
                                "id": cid, "name": c["name"],
                                "desc": c["desc"], "icon": c["icon"],
                            })
                        await send({"type": "rogue_offer", "cards": cards_data})
                        # Game waits for card selection before AI moves
                    else:
                        if not two_player and engine.ready:
                            if game.ai_color == game.current_player and handicap == 0:
                                await _ai_move(game, send)

                    if not game.game_over and engine.ready:
                        asyncio.create_task(do_analysis_bg(game))

                # ── play ──────────────────────────────────────────────────────
                elif action == "play":
                    if not game:
                        game = active_games.get(game_id)
                    if not game or game.game_over:
                        await send_error("暂无进行中的对局")
                        continue

                    if game.two_player:
                        color = game.current_player
                    else:
                        if not engine.ready:
                            snapshot = _engine_state_snapshot()
                            await send_error(
                                snapshot.get("message")
                                or "KataGo尚未就绪，当前不能进行 AI 对局"
                            )
                            continue
                        if game.current_player != game.player_color:
                            await send_error("还没轮到你")
                            continue
                        color = game.player_color

                    # ── Ultimate mode play ─────────────────────────────────
                    if game.ultimate and not game.two_player:
                        x, y = int(data["x"]), int(data["y"])

                        if game.ultimate_ai_card == "territory":
                            cv_player = 1 if color == "B" else 2
                            fb = _ultimate_get_territory_forbidden(
                                game, cv_player)
                            if (x, y) in fb:
                                await send_error("这里已被绝对领地封锁，不能在 AI 的禁区内落子")
                                continue

                        if game.board[y][x] != 0:
                            await send_error("该位置已有棋子")
                            continue

                        was_double_pending = game.ultimate_double_pending
                        game.ultimate_move_count += 1
                        gtp = coord_to_gtp(x, y, game.size)
                        game.moves.append((color, gtp))
                        game.place_stone(x, y, color)
                        game.passed[color] = False

                        p_card = game.ultimate_player_card
                        if p_card == "quickthink":
                            if not game.ultimate_quickthink_active:
                                game.ultimate_quickthink_token += 1
                            game.ultimate_quickthink_active = True
                            game.current_player = game.player_color
                            await send({"type": "game_state", **game.to_state()})
                            if game.ultimate_move_count >= 20:
                                game.ultimate_quickthink_active = False
                                await _ultimate_force_score(game, send)
                            continue

                        if p_card:
                            await _apply_ultimate_effect(game, send, x, y, color, p_card)

                        chain_bonus = (
                            p_card == "chain"
                            and random.random() < ULTIMATE_CHAIN_EXTRA_TURN_CHANCE
                        )
                        double_bonus = (
                            p_card == "double"
                            and not was_double_pending
                        )

                        game.ultimate_extra_turn = chain_bonus or double_bonus
                        game.ultimate_double_pending = bool(double_bonus)
                        game.current_player = (
                            game.player_color if (chain_bonus or double_bonus) else game.ai_color
                        )
                        await send({"type": "game_state", **game.to_state()})

                        if game.ultimate_move_count >= 20:
                            await _ultimate_force_score(game, send)
                            continue

                        if chain_bonus:
                            await send({"type": "rogue_event", "msg": "连珠棋触发成功，你可以继续落子"})
                            continue

                        if double_bonus:
                            await send({"type": "rogue_event", "msg": "双刀流触发成功，你可以继续落子"})
                            continue

                        game.ultimate_extra_turn = False
                        if engine.ready:
                            await _ultimate_ai_move(game, send)
                        if not game.game_over and engine.ready:
                            asyncio.create_task(do_analysis_bg(game))
                        continue

                    # Rogue: 让子棋任务 - force pass for opening passes
                    if (game.rogue_card == "handicap_quest"
                            and not game.two_player
                            and game.rogue_handicap_passes < ROGUE_HANDICAP_REQUIRED_PASSES):
                        await send_error(
                            f"🏋️ 让子棋任务：还需虚手 "
                            f"{ROGUE_HANDICAP_REQUIRED_PASSES - game.rogue_handicap_passes} 次才能落子")
                        continue

                    x, y = int(data["x"]), int(data["y"])
                    gtp = coord_to_gtp(x, y, game.size)

                    if game.board[y][x] != 0:
                        await send_error("该位置已有棋子")
                        continue

                    player_forbidden = _get_ai_rogue_forbidden_points(game)
                    if not game.two_player and (x, y) in player_forbidden:
                        await send_error("这里已被 AI 的 Rogue 卡限制，当前不能落子")
                        continue

                    if engine.ready:
                        resp = await run_in_executor(
                            engine.send_command, f"play {color} {gtp}")
                        if "?" in resp:
                            await send_error(f"无效落子: {gtp}")
                            continue

                    game.moves.append((color, gtp))
                    captured = game.place_stone(x, y, color)
                    game.passed[color] = False
                    game.current_player = "W" if color == "B" else "B"
                    await _apply_player_rogue_move_effects(
                        game, send, x, y, color, captured)
                    await _apply_ai_rogue_response_effects(
                        game, send, x, y, color)

                    quickthink_bonus = False
                    if game.rogue_card == "quickthink" and not game.two_player:
                        if game.rogue_quickthink_stage == 1:
                            game.rogue_quickthink_stage = 2
                            game.current_player = game.player_color
                            quickthink_bonus = True
                        else:
                            game.rogue_quickthink_stage = 0

                    await send({"type": "game_state", **game.to_state()})

                    # Rogue: skip AI turn (twin / exchange / handicap_quest)
                    if game.rogue_skip_ai:
                        game.rogue_skip_ai = False
                        game.current_player = game.player_color
                        await send({"type": "game_state", **game.to_state()})
                        skip_msgs = {
                            "twin": "⚡ 双子星辰！你可以继续落子",
                            "exchange": "🔄 乾坤挪移！你可以继续落子",
                            "handicap_quest": "🏋️ 奖励回合！你可以继续落子",
                        }
                        await send({"type": "rogue_event",
                                    "msg": skip_msgs.get(game.rogue_card,
                                                         "你可以继续落子")})
                    elif not game.two_player and engine.ready:
                        if quickthink_bonus:
                            await send({"type": "rogue_event",
                                        "msg": "⚡ 快速思考：2 秒追加手已开启"})
                        else:
                            await _ai_move(game, send)

                    if not game.game_over and engine.ready:
                        asyncio.create_task(do_analysis_bg(game))

                # ── pass ──────────────────────────────────────────────────────
                elif action == "pass":
                    if not game:
                        game = active_games.get(game_id)
                    if not game or game.game_over:
                        continue

                    if game.two_player:
                        color = game.current_player
                    else:
                        if game.current_player != game.player_color:
                            continue
                        color = game.player_color

                    # Ultimate mode pass
                    if game.ultimate and not game.two_player:
                        if game.ultimate_player_card == "quickthink" and game.ultimate_quickthink_active:
                            game.ultimate_quickthink_active = False
                            game.current_player = game.ai_color
                            await send({"type": "game_state", **game.to_state()})
                            if game.ultimate_move_count >= 20:
                                await _ultimate_force_score(game, send)
                            elif engine.ready:
                                await _ultimate_ai_move(game, send)
                            if not game.game_over and engine.ready:
                                asyncio.create_task(do_analysis_bg(game))
                            continue
                        game.ultimate_move_count += 1
                        game.moves.append((color, "pass"))
                        game.passed[color] = True
                        game.current_player = "W" if color == "B" else "B"
                        game.ultimate_double_pending = False
                        await send({"type": "game_state", **game.to_state()})
                        if game.ultimate_move_count >= 20:
                            await _ultimate_force_score(game, send)
                        elif engine.ready:
                            await _ultimate_ai_move(game, send)
                        if not game.game_over and engine.ready:
                            asyncio.create_task(do_analysis_bg(game))
                        continue

                    if engine.ready:
                        await run_in_executor(
                            engine.send_command, f"play {color} pass")
                    game.moves.append((color, "pass"))
                    game.passed[color] = True
                    game.current_player = "W" if color == "B" else "B"
                    if game.rogue_card == "quickthink":
                        game.rogue_quickthink_stage = 0

                    # Rogue: 让子棋任务 — track opening passes
                    if (game.rogue_card == "handicap_quest"
                            and not game.two_player
                            and color == game.player_color
                            and not game.rogue_handicap_active):
                        game.rogue_handicap_passes += 1
                        if game.rogue_handicap_passes >= ROGUE_HANDICAP_REQUIRED_PASSES:
                            game.rogue_handicap_active = True
                            await send({"type": "rogue_event",
                                        "msg": "🏋️ 让子棋任务完成！"
                                               f"现在每 {ROGUE_HANDICAP_BONUS_INTERVAL} 手可多下一手"})
                        else:
                            await send({"type": "rogue_event",
                                        "msg": f"🏋️ 虚手 "
                                               f"{game.rogue_handicap_passes}/"
                                               f"{ROGUE_HANDICAP_REQUIRED_PASSES}"})

                    await send({"type": "game_state", **game.to_state()})

                    if not game.two_player and engine.ready:
                        await _ai_move(game, send)

                    if not game.game_over and engine.ready:
                        asyncio.create_task(do_analysis_bg(game))

                # ── undo ──────────────────────────────────────────────────────
                elif action == "undo":
                    if not game:
                        game = active_games.get(game_id)
                    if not game or not game.moves:
                        continue
                    if game.rogue_card == "no_regret":
                        await send_error("这张卡会禁用悔棋")
                        continue

                    undo_count = 1 if game.two_player else (
                        2 if len(game.moves) >= 2 else 1)
                    for _ in range(undo_count):
                        if game.moves:
                            if engine.ready:
                                await run_in_executor(
                                    engine.send_command, "undo")
                            game.moves.pop()

                    game.current_player = game.player_color if not game.two_player \
                        else ("B" if len(game.moves) % 2 == 0 else "W")
                    game.game_over = False
                    game.rebuild_board()
                    if game.rogue_card == "foolish_wisdom":
                        game.rogue_fool_shapes = set()
                    if game.ultimate_player_card == "foolish_wisdom":
                        game.ultimate_fool_shapes = set()
                    _prepare_player_turn_modifiers(game)
                    await send({"type": "game_state", **game.to_state()})

                    if engine.ready:
                        analysis = await do_analysis(game)
                        await send({"type": "analysis", **analysis})

                # ── resign ────────────────────────────────────────────────────
                elif action == "resign":
                    if not game:
                        game = active_games.get(game_id)
                    if not game:
                        continue
                    game.game_over = True
                    game.winner = game.ai_color if not game.two_player \
                        else ("W" if game.current_player == "B" else "B")
                    await send({
                        "type": "game_over",
                        "winner": game.winner,
                        "score": None,
                        "reason": "resign",
                    })

                # ── request_hint ──────────────────────────────────────────────
                elif action == "request_hint":
                    if not game:
                        game = active_games.get(game_id)
                    if not game or game.game_over or not engine.ready:
                        continue
                    analysis = await do_analysis(game)
                    await send({"type": "analysis", **analysis})

                # ── set_level ─────────────────────────────────────────────────
                elif action == "set_level":
                    if not game:
                        game = active_games.get(game_id)
                    if not game:
                        continue
                    level = data.get("level", "a3d")
                    game.level = level
                    if engine.ready:
                        _m = "ultimate" if game.ultimate else ("rogue" if game.rogue_card else "normal")
                        visits = get_game_visits(level, len(game.moves), mode=_m)
                        await run_in_executor(engine.set_visits, visits)
                    await send({"type": "level_set", "level": level})

                # ── load_position (review / SGF analysis) ────────────────────
                elif action == "load_position":
                    size = int(data.get("size", 19))
                    komi = float(data.get("komi", 7.5))
                    moves_list = data.get("moves", [])

                    if engine.ready:
                        await run_in_executor(
                            engine.send_command, f"boardsize {size}")
                        await run_in_executor(
                            engine.send_command, "clear_board")
                        await run_in_executor(
                            engine.send_command, f"komi {komi}")
                        for move in moves_list:
                            c, g = move[0], move[1]
                            await run_in_executor(
                                engine.send_command, f"play {c} {g}")

                        next_color = "B" if len(moves_list) % 2 == 0 else "W"
                        temp = GoGame(size, komi, 0, "B", "a3d")
                        temp.current_player = next_color
                        for move in moves_list:
                            temp.moves.append((move[0], move[1]))
                        temp.rebuild_board()

                        result = await do_analysis(temp)
                        await send({"type": "analysis", **result})

                # ── time_expired ─────────────────────────────────────────────
                elif action == "time_expired":
                    if not game:
                        game = active_games.get(game_id)
                    if not game or game.game_over:
                        continue
                    loser = data.get("color", "B")
                    winner = "W" if loser == "B" else "B"
                    game.game_over = True
                    game.winner = winner
                    await send({
                        "type": "game_over",
                        "winner": winner,
                        "score": f"{winner}+T",
                        "reason": "timeout",
                    })

                # ── rogue_select_card ─────────────────────────────────────────
                elif action == "rogue_select_card":
                    if not game:
                        game = active_games.get(game_id)
                    if not game:
                        continue
                    card_id = data.get("card_id", "")
                    if card_id not in ROGUE_CARDS:
                        continue
                    await _activate_rogue_card(game, send, card_id)
                    if game.ai_rogue_enabled and not game.two_player:
                        ai_card_id = pick_ai_rogue_card(exclude=[card_id])
                        await _activate_ai_rogue_card(game, send, ai_card_id)
                    # If not seal (which needs setup), start AI move
                    if card_id != "seal":
                        if not game.two_player and engine.ready and game.ai_color == game.current_player:
                            await _ai_move(game, send)
                        if not game.game_over and engine.ready:
                            asyncio.create_task(do_analysis_bg(game))

                # ── rogue_seal_point ─────────────────────────────────────────
                elif action == "rogue_seal_point":
                    if not game:
                        game = active_games.get(game_id)
                    if not game or not game.rogue_waiting_seal:
                        continue
                    x, y = int(data["x"]), int(data["y"])
                    if (x, y) not in game.rogue_seal_points:
                        game.rogue_seal_points.append((x, y))
                    await send({"type": "rogue_seal_update",
                                "points": [[px, py]
                                           for px, py in game.rogue_seal_points],
                                "remaining": 3 - len(game.rogue_seal_points)})
                    if len(game.rogue_seal_points) >= 3:
                        game.rogue_waiting_seal = False
                        await send({"type": "rogue_seal_done"})
                        if engine.ready and game.ai_color == game.current_player:
                            await _ai_move(game, send)
                        if not game.game_over and engine.ready:
                            asyncio.create_task(do_analysis_bg(game))

                # ── rogue_use_puppet ─────────────────────────────────────────
                elif action == "rogue_use_puppet":
                    if not game:
                        game = active_games.get(game_id)
                    if not game or game.game_over or not engine.ready:
                        continue
                    if game.rogue_card != "puppet" or \
                       game.rogue_uses.get("puppet", 0) <= 0:
                        await send_error("傀儡术已用完")
                        continue
                    if game.current_player != game.player_color:
                        await send_error("还没轮到你")
                        continue
                    x, y = int(data["x"]), int(data["y"])
                    gtp = coord_to_gtp(x, y, game.size)
                    ai_color = game.ai_color
                    # Play the move for AI at player's chosen point
                    resp = await run_in_executor(
                        engine.send_command,
                        f"play {ai_color} {gtp}")
                    if "?" in resp:
                        await send_error(f"该位置无法落子: {gtp}")
                        continue
                    game.rogue_uses["puppet"] -= 1
                    game.moves.append((ai_color, gtp))
                    game.place_stone(x, y, ai_color)
                    game.passed[ai_color] = False
                    game.current_player = game.player_color
                    await send({"type": "game_state", **game.to_state()})
                    await send({"type": "ai_move", "gtp": gtp,
                                "color": ai_color, "x": x, "y": y})
                    await send({"type": "rogue_event",
                                "msg": f"🎭 傀儡术！你替 AI 落子于 {gtp}"})
                    await send({"type": "rogue_uses_update",
                                "uses": game.rogue_uses})
                    if not game.game_over and engine.ready:
                        asyncio.create_task(do_analysis_bg(game))

                # ── rogue_use_twin ───────────────────────────────────────────
                elif action == "rogue_use_twin":
                    if not game:
                        game = active_games.get(game_id)
                    if not game or game.game_over:
                        continue
                    if game.rogue_card != "twin" or \
                       game.rogue_uses.get("twin", 0) <= 0:
                        await send_error("双子星辰已用完")
                        continue
                    game.rogue_uses["twin"] -= 1
                    game.rogue_skip_ai = True
                    await send({"type": "rogue_event",
                                "msg": f"⚡ 双子星辰激活！下一手后可连续落子"
                                       f"（剩余 {game.rogue_uses.get('twin',0)} 次）"})
                    await send({"type": "rogue_uses_update",
                                "uses": game.rogue_uses})

                # ── rogue_use_exchange ───────────────────────────────────────
                elif action == "rogue_use_exchange":
                    if not game:
                        game = active_games.get(game_id)
                    if not game or game.game_over:
                        continue
                    if game.rogue_card != "exchange" or \
                       game.rogue_uses.get("exchange", 0) <= 0:
                        await send_error("乾坤挪移已用完")
                        continue
                    game.rogue_uses["exchange"] -= 1
                    game.rogue_skip_ai = True
                    await send({"type": "rogue_event",
                                "msg": "🔄 乾坤挪移激活！AI 下次将被迫虚手"})
                    await send({"type": "rogue_uses_update",
                                "uses": game.rogue_uses})

                # ── ultimate_select_card ──────────────────────────────────────
                elif action == "ultimate_select_card":
                    if not game:
                        game = active_games.get(game_id)
                    if not game or not game.ultimate:
                        continue
                    card_id = data.get("card_id", "")
                    if card_id not in ULTIMATE_CARDS:
                        continue
                    game.ultimate_player_card = card_id
                    game.ultimate_joseki_targets = []
                    game.ultimate_joseki_hits = 0
                    game.ultimate_joseki_done = False
                    game.ultimate_godhand_center = None
                    game.ultimate_godhand_trigger = []
                    game.ultimate_godhand_done = False
                    game.ultimate_corner_helper_done = False
                    game.ultimate_sanrensei_done = False
                    game.ultimate_quickthink_active = False
                    game.ultimate_fool_shapes = set()
                    if card_id == "joseki_burst":
                        game.ultimate_joseki_targets = _pick_joseki_targets(
                            game.size, ULTIMATE_JOSEKI_TARGET_COUNT)
                    elif card_id == "god_hand":
                        rng = random.Random(time.time_ns())
                        game.ultimate_godhand_center = _random_hidden_center(game.size, 2, rng)
                        game.ultimate_godhand_trigger = _diamond_points(
                            game.ultimate_godhand_center[0],
                            game.ultimate_godhand_center[1],
                            2,
                            game.size,
                        )
                    elif card_id == "quickthink" and game.current_player == game.player_color:
                        game.ultimate_quickthink_token += 1
                        game.ultimate_quickthink_active = True
                    pdef = ULTIMATE_CARDS[card_id]
                    ai_card_id = pick_ai_ultimate_card(exclude=[card_id])
                    game.ultimate_ai_card = ai_card_id
                    adef = ULTIMATE_CARDS[ai_card_id]
                    await send({"type": "ultimate_cards_selected",
                                "player_card": card_id,
                                "player_name": pdef["name"],
                                "player_icon": pdef["icon"],
                                "ai_card": ai_card_id,
                                "ai_name": adef["name"],
                                "ai_icon": adef["icon"],
                                **game.to_state()})
                    if card_id == "joseki_burst":
                        pts = ", ".join(
                            coord_to_gtp(px, py, game.size)
                            for px, py in game.ultimate_joseki_targets
                        )
                        await send({"type": "rogue_event",
                                    "msg": f"定式爆发已点亮目标点：{pts}。命中其中 3 个后会触发爆发"})
                    if engine.ready and game.ai_color == game.current_player:
                        await _ultimate_ai_move(game, send)
                    if not game.game_over and engine.ready:
                        asyncio.create_task(do_analysis_bg(game))

                elif action == "ultimate_quickthink_end":
                    if not game:
                        game = active_games.get(game_id)
                    if not game or not game.ultimate:
                        continue
                    if game.ultimate_player_card != "quickthink" or not game.ultimate_quickthink_active:
                        continue
                    game.ultimate_quickthink_active = False
                    game.current_player = game.ai_color
                    await send({"type": "game_state", **game.to_state()})
                    if game.ultimate_move_count >= 20:
                        await _ultimate_force_score(game, send)
                    elif engine.ready:
                        await _ultimate_ai_move(game, send)
                    if not game.game_over and engine.ready:
                        asyncio.create_task(do_analysis_bg(game))

                # ── score ─────────────────────────────────────────────────────
                elif action == "score":
                    if not game:
                        game = active_games.get(game_id)
                    if not game:
                        continue
                    if engine.ready:
                        resp = await run_in_executor(
                            engine.send_command, "final_score")
                        score_str = resp.replace("=", "").strip()
                    else:
                        score_str = "?"
                    winner = ("B" if score_str.startswith("B") else
                              "W" if score_str.startswith("W") else "draw")
                    game.game_over = True
                    game.winner = winner
                    await send({
                        "type": "game_over",
                        "winner": winner,
                        "score": score_str,
                        "reason": "score",
                    })

            except Exception as e:
                import traceback
                print(f"[WS {game_id}] Action error ({action}): {e}")
                traceback.print_exc()
                try:
                    await send_error(f"处理出错: {e}")
                except Exception:
                    pass

    except WebSocketDisconnect:
        pass  # Keep game state for reconnection
    except Exception as e:
        print(f"[WS {game_id}] Fatal error: {e}")
        try:
            await send({"type": "error", "message": f"服务器错误: {e}"})
        except Exception:
            pass


def _get_star_points(size: int) -> list[tuple[int, int]]:
    """Return star points + tengen for a given board size."""
    if size == 19:
        pts = [(3, 3), (9, 3), (15, 3), (3, 9), (9, 9), (15, 9),
               (3, 15), (9, 15), (15, 15)]
    elif size == 13:
        pts = [(3, 3), (6, 3), (9, 3), (3, 6), (6, 6), (9, 6),
               (3, 9), (6, 9), (9, 9)]
    elif size == 9:
        pts = [(2, 2), (4, 2), (6, 2), (2, 4), (4, 4), (6, 4),
               (2, 6), (4, 6), (6, 6)]
    else:
        c = size // 2
        pts = [(c, c)]
    return pts


def _get_blackhole_points(size: int) -> list[tuple[int, int]]:
    """Return a diamond (manhattan ≤ 2) centered on tengen = 13 points."""
    c = size // 2
    pts = []
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if abs(dx) + abs(dy) <= 2:
                nx, ny = c + dx, c + dy
                if 0 <= nx < size and 0 <= ny < size:
                    pts.append((nx, ny))
    return pts


def _get_golden_corner_points(size: int, corner: int) -> list[tuple[int, int]]:
    """Return 4x4 forbidden zone for a corner (0=TL, 1=TR, 2=BL, 3=BR)."""
    pts = []
    for dy in range(4):
        for dx in range(4):
            if corner == 0:
                pts.append((dx, dy))
            elif corner == 1:
                pts.append((size - 1 - dx, dy))
            elif corner == 2:
                pts.append((dx, size - 1 - dy))
            else:
                pts.append((size - 1 - dx, size - 1 - dy))
    return pts


def _get_sansan_points(size: int) -> list[tuple[int, int]]:
    """Return all four 3-3 points."""
    return [(2, 2), (size - 3, 2), (2, size - 3), (size - 3, size - 3)]


def _pick_joseki_targets(size: int, n: int = 8) -> list[tuple[int, int]]:
    """Pick n joseki-ish corner points for joseki_ocd."""
    import time
    rng = random.Random(time.time_ns())
    offsets = [(2, 2), (2, 3), (3, 2), (3, 3), (2, 4), (4, 2), (3, 4), (4, 3)]
    candidates = []
    for bx in (0, size - 1):
        for by in (0, size - 1):
            for ox, oy in offsets:
                x = ox if bx == 0 else size - 1 - ox
                y = oy if by == 0 else size - 1 - oy
                if 0 <= x < size and 0 <= y < size:
                    candidates.append((x, y))
    candidates = list(dict.fromkeys(candidates))
    rng.shuffle(candidates)
    return candidates[:n]


def _is_lowline(x: int, y: int, size: int) -> bool:
    """Check if a coord is on the 3rd line or lower (edge-adjacent)."""
    return x <= 2 or x >= size - 3 or y <= 2 or y >= size - 3


def _mirror_coord(x: int, y: int, size: int) -> tuple[int, int]:
    """Mirror a coordinate about tengen (center)."""
    return (size - 1 - x, size - 1 - y)


def _adjacent_points(x: int, y: int, size: int) -> list[tuple[int, int]]:
    """Return orthogonally adjacent points within the board."""
    pts = []
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nx, ny = x + dx, y + dy
        if 0 <= nx < size and 0 <= ny < size:
            pts.append((nx, ny))
    return pts


def _adjacent8_points(x: int, y: int, size: int) -> list[tuple[int, int]]:
    """Return the 8 neighboring points around a coordinate."""
    pts = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < size and 0 <= ny < size:
                pts.append((nx, ny))
    return pts


def _set_points_to_color(game: GoGame, points: list[tuple[int, int]], color: str) -> list[tuple[int, int]]:
    """Directly set a batch of points to color without capture logic."""
    cv = 1 if color == "B" else 2
    changed = []
    for x, y in points:
        if game.board[y][x] != cv:
            game.board[y][x] = cv
            changed.append((x, y))
    return changed


def _collect_joseki_burst_points(
    game: GoGame,
    anchors: list[tuple[int, int]],
    color: str,
    count: int,
    rng: random.Random,
) -> list[tuple[int, int]]:
    """Collect flashy bonus points around joseki anchors for ultimate mode."""
    cv = 1 if color == "B" else 2
    nearby = []
    seen = set()
    for ax, ay in anchors:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                nx, ny = ax + dx, ay + dy
                if 0 <= nx < game.size and 0 <= ny < game.size:
                    if (nx, ny) in seen or game.board[ny][nx] == cv:
                        continue
                    seen.add((nx, ny))
                    nearby.append((nx, ny))
    rng.shuffle(nearby)
    chosen = nearby[:count]
    if len(chosen) < count:
        leftovers = [
            (x, y)
            for y in range(game.size)
            for x in range(game.size)
            if game.board[y][x] != cv and (x, y) not in seen
        ]
        rng.shuffle(leftovers)
        chosen.extend(leftovers[: count - len(chosen)])
    return chosen


def _diamond_points(
    cx: int,
    cy: int,
    radius: int,
    size: int,
    *,
    boundary_only: bool = False,
    include_center: bool = True,
) -> list[tuple[int, int]]:
    pts = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            dist = abs(dx) + abs(dy)
            if dist > radius:
                continue
            if boundary_only and dist != radius:
                continue
            if not include_center and dist == 0:
                continue
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < size and 0 <= ny < size:
                pts.append((nx, ny))
    return pts


def _get_square_points(cx: int, cy: int, radius: int, size: int) -> list[tuple[int, int]]:
    pts = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < size and 0 <= ny < size:
                pts.append((nx, ny))
    return pts


def _pick_fog_mask(size: int, rng: random.Random) -> list[tuple[int, int]]:
    cx = rng.randint(0, size - 1)
    cy = rng.randint(0, size - 1)
    return _get_square_points(cx, cy, ROGUE_FOG_MASK_RADIUS, size)


def _shape_key(points: list[tuple[int, int]] | tuple[tuple[int, int], ...]) -> tuple[tuple[int, int], ...]:
    return tuple(sorted(points))


def _shape_center(shape: tuple[tuple[int, int], ...]) -> tuple[int, int]:
    xs = [x for x, _ in shape]
    ys = [y for _, y in shape]
    return ((min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2)


def _find_new_fool_shapes(
    game: GoGame,
    color: str,
    seen_shapes: set[tuple[tuple[int, int], ...]],
) -> list[tuple[tuple[int, int], ...]]:
    cv = 1 if color == "B" else 2
    found = []
    found_keys = set()
    orientations = [
        ((1, 0), (0, 1)),
        ((-1, 0), (0, 1)),
        ((1, 0), (0, -1)),
        ((-1, 0), (0, -1)),
    ]

    for y in range(game.size):
        for x in range(game.size):
            if game.board[y][x] != cv:
                continue
            for (ax, ay), (bx, by) in orientations:
                p1 = (x + ax, y + ay)
                p2 = (x + bx, y + by)
                if not (0 <= p1[0] < game.size and 0 <= p1[1] < game.size):
                    continue
                if not (0 <= p2[0] < game.size and 0 <= p2[1] < game.size):
                    continue
                if game.board[p1[1]][p1[0]] != cv or game.board[p2[1]][p2[0]] != cv:
                    continue
                diag = (x + ax + bx, y + ay + by)
                if 0 <= diag[0] < game.size and 0 <= diag[1] < game.size:
                    if game.board[diag[1]][diag[0]] == cv:
                        continue
                shape = _shape_key([(x, y), p1, p2])
                if shape in seen_shapes or shape in found_keys:
                    continue
                isolated = True
                shape_set = set(shape)
                for sx, sy in shape:
                    for nx, ny in _adjacent8_points(sx, sy, game.size):
                        if (nx, ny) in shape_set:
                            continue
                        if game.board[ny][nx] == cv:
                            isolated = False
                            break
                    if not isolated:
                        break
                if not isolated:
                    continue
                found.append(shape)
                found_keys.add(shape)

    return found


def _random_hidden_center(size: int, radius: int, rng: random.Random) -> tuple[int, int]:
    low = max(radius, 0)
    high = max(low, size - radius - 1)
    return (rng.randint(low, high), rng.randint(low, high))


def _get_corner_square_points(size: int, corner: int, span: int) -> list[tuple[int, int]]:
    pts = []
    for dy in range(span):
        for dx in range(span):
            if corner == 0:
                pts.append((dx, dy))
            elif corner == 1:
                pts.append((size - span + dx, dy))
            elif corner == 2:
                pts.append((dx, size - span + dy))
            else:
                pts.append((size - span + dx, size - span + dy))
    return pts


def _get_corner_helper_spawn_points(size: int, corner: int, span: int = 5) -> list[tuple[int, int]]:
    inner = span - 1
    min_line = 2
    pts = []
    if corner == 0:
        pts.extend((x, inner) for x in range(min_line, span))
        pts.extend((inner, y) for y in range(min_line, span - 1))
    elif corner == 1:
        pts.extend((x, inner) for x in range(size - span, size - min_line))
        pts.extend((size - span, y) for y in range(min_line, span - 1))
    elif corner == 2:
        pts.extend((x, size - span) for x in range(min_line, span))
        pts.extend((inner, y) for y in range(size - span + 1, size - min_line))
    else:
        pts.extend((x, size - span) for x in range(size - span, size - min_line))
        pts.extend((size - span, y) for y in range(size - span + 1, size - min_line))
    return list(dict.fromkeys(pts))


def _get_corner_boundary_points(size: int, corner: int, span: int) -> list[tuple[int, int]]:
    pts = []
    for x, y in _get_corner_square_points(size, corner, span):
        min_x = 0 if corner in (0, 2) else size - span
        max_x = span - 1 if corner in (0, 2) else size - 1
        min_y = 0 if corner in (0, 1) else size - span
        max_y = span - 1 if corner in (0, 1) else size - 1
        if x in (min_x, max_x) or y in (min_y, max_y):
            pts.append((x, y))
    return pts


def _find_corner_with_min_stones(game: GoGame, color: str, span: int, count: int) -> Optional[int]:
    cv = 1 if color == "B" else 2
    for corner in range(4):
        own = sum(
            1
            for x, y in _get_corner_square_points(game.size, corner, span)
            if game.board[y][x] == cv
        )
        if own >= count:
            return corner
    return None


def _player_non_pass_coords(game: GoGame, color: str, limit: Optional[int] = None) -> list[tuple[int, int]]:
    coords = []
    for move_color, gtp in game.moves:
        if move_color != color or gtp.upper() == "PASS":
            continue
        coord = gtp_to_coord(gtp, game.size)
        if coord:
            coords.append(coord)
        if limit is not None and len(coords) >= limit:
            break
    return coords


def _get_ai_rogue_forbidden_points(game: GoGame) -> list[tuple[int, int]]:
    card = game.ai_rogue_card
    if card in {"blackhole", "golden_corner", "fog"}:
        return list(game.ai_rogue_seal_points)
    return []


def _refresh_ai_rogue_player_turn(game: GoGame):
    if game.two_player or not game.ai_rogue_enabled:
        return
    if game.ai_rogue_card == "fog":
        if game.current_player == game.player_color:
            rng = random.Random(time.time_ns())
            game.ai_rogue_seal_points = _pick_fog_mask(game.size, rng)
        else:
            game.ai_rogue_seal_points = []


def _prepare_player_turn_modifiers(game: GoGame):
    if game.two_player or game.current_player != game.player_color:
        return
    _refresh_ai_rogue_player_turn(game)
    if game.rogue_card == "quickthink" and game.rogue_quickthink_stage == 0:
        game.rogue_quickthink_stage = 1
    if game.ultimate and game.ultimate_player_card == "quickthink" and not game.ultimate_quickthink_active:
        game.ultimate_quickthink_token += 1
        game.ultimate_quickthink_active = True


def _clear_player_turn_modifiers(game: GoGame):
    game.rogue_quickthink_stage = 0
    game.ultimate_quickthink_active = False


async def _pick_second_best_point(game: GoGame, color: str) -> Optional[tuple[int, int]]:
    if not engine.ready:
        return None

    def _analyze():
        visits = max(120, min(get_game_visits(game.level, len(game.moves), mode="rogue"), 800))
        lines, _ = engine.analyze(
            color,
            visits=visits,
            interval=40,
            duration=1.2,
            extra_args=["rootInfo", "true"],
        )
        result = engine.parse_analysis(lines, [], game.size, to_move_color=color)
        return result.get("top_moves", [])

    try:
        top_moves = await run_in_executor(_analyze)
    except Exception:
        return None

    for candidate in top_moves[1:]:
        move = candidate.get("move") or candidate.get("gtp")
        if not move or move.upper() == "PASS":
            continue
        coord = gtp_to_coord(move, game.size)
        if coord and game.board[coord[1]][coord[0]] == 0:
            return coord
    return None


async def _activate_rogue_card(game: GoGame, send_fn, card_id: str):
    """Apply immediate effects when the player picks a rogue card."""
    cdef = ROGUE_CARDS[card_id]
    game.rogue_card = card_id
    game.rogue_joseki_targets = []
    game.rogue_joseki_hits = 0
    game.rogue_joseki_done = False
    game.rogue_godhand_center = None
    game.rogue_godhand_trigger = []
    game.rogue_godhand_done = False
    game.rogue_sansan_trap_done = False
    game.rogue_corner_helper_done = False
    game.rogue_sanrensei_done = False
    game.rogue_quickthink_stage = 0
    game.rogue_fool_shapes = set()
    if card_id != "seal":
        game.rogue_waiting_seal = False
    if card_id not in {"seal", "blackhole", "golden_corner", "fog"}:
        game.rogue_seal_points = []
    if "uses" in cdef:
        game.rogue_uses[card_id] = cdef["uses"]

    if card_id == "komi_relief":
        game.komi = max(0.5, game.komi - 5.0)
        if engine.ready:
            await run_in_executor(engine.send_command, f"komi {game.komi}")
    elif card_id == "seal":
        game.rogue_waiting_seal = True
    elif card_id == "blackhole":
        game.rogue_seal_points = _get_blackhole_points(game.size)
    elif card_id == "golden_corner":
        corner = random.randint(0, 3)
        game.rogue_seal_points = _get_golden_corner_points(game.size, corner)
        corner_names = ["左上角", "右上角", "左下角", "右下角"]
        await send_fn({"type": "rogue_event",
                       "msg": f"黄金角已封锁 {corner_names[corner]} 的 4x4 区域"})
    elif card_id == "joseki_ocd":
        game.rogue_joseki_targets = _pick_joseki_targets(
            game.size, ROGUE_JOSEKI_TARGET_COUNT)
        pts_str = ", ".join(
            coord_to_gtp(px, py, game.size)
            for px, py in game.rogue_joseki_targets)
        await send_fn({"type": "rogue_event",
                       "msg": f"定式强迫症已点亮 {ROGUE_JOSEKI_TARGET_COUNT} 个目标点：{pts_str}。"
                              f"命中其中 {ROGUE_JOSEKI_REQUIRED_HITS} 个后会自动补满剩余点位"})
    elif card_id == "handicap_quest":
        await send_fn({"type": "rogue_event",
                       "msg": f"让子任务开始：你需要先虚手 {ROGUE_HANDICAP_REQUIRED_PASSES} 次，"
                              f"之后每下满 {ROGUE_HANDICAP_BONUS_INTERVAL} 手可再让 AI 虚手一次"})
    elif card_id == "god_hand":
        rng = random.Random(time.time_ns())
        game.rogue_godhand_center = _random_hidden_center(game.size, 2, rng)
        game.rogue_godhand_trigger = _diamond_points(
            game.rogue_godhand_center[0], game.rogue_godhand_center[1], 1, game.size)
    elif card_id == "quickthink" and game.current_player == game.player_color:
        game.rogue_quickthink_stage = 1

    await send_fn({"type": "rogue_card_selected",
                   "card_id": card_id,
                   "name": cdef["name"],
                   "icon": cdef["icon"],
                   "waiting_seal": card_id == "seal",
                   **game.to_state()})


async def _activate_ai_rogue_card(game: GoGame, send_fn, card_id: str):
    cdef = ROGUE_CARDS[card_id]
    game.ai_rogue_enabled = True
    game.ai_rogue_card = card_id
    game.ai_rogue_seal_points = []
    game.ai_rogue_sansan_trap_done = False

    if card_id == "blackhole":
        game.ai_rogue_seal_points = _get_blackhole_points(game.size)
    elif card_id == "golden_corner":
        corner = random.randint(0, 3)
        game.ai_rogue_seal_points = _get_golden_corner_points(game.size, corner)
    elif card_id == "fog":
        _refresh_ai_rogue_player_turn(game)

    await send_fn({
        "type": "rogue_ai_selected",
        "card_id": card_id,
        "name": cdef["name"],
        "icon": cdef["icon"],
        **game.to_state(),
    })


async def _apply_player_rogue_move_effects(game: GoGame, send_fn,
                                           x: int, y: int,
                                           color: str, captured: int):
    """Apply player-side rogue effects after a successful move."""
    if game.rogue_card == "erosion" and captured > 0:
        shift = 2.0 * captured
        owner_color = color if game.two_player else game.player_color
        if owner_color == "B":
            game.komi -= shift
        else:
            game.komi += shift
        if engine.ready:
            await run_in_executor(engine.send_command, f"komi {game.komi}")
        await send_fn({"type": "rogue_event",
                       "msg": f"蚕食触发：提掉 {captured} 子，当前贴目变为 {game.komi}"})

    if game.rogue_card == "sprout":
        color_moves = sum(1 for c, m in game.moves if c == color and m.upper() != "PASS")
        if color_moves <= 1:
            adj = _adjacent_points(x, y, game.size)
            empty_adj = [(ax, ay) for ax, ay in adj if game.board[ay][ax] == 0]
            if empty_adj:
                bx, by = random.choice(empty_adj)
                b_gtp = coord_to_gtp(bx, by, game.size)
                if engine.ready:
                    r = await run_in_executor(
                        engine.send_command,
                        f"play {color} {b_gtp}")
                    if "?" not in r:
                        game.place_stone(bx, by, color)
                        game.moves.append((color, b_gtp))
                        await send_fn({"type": "rogue_event",
                                       "msg": f"萌芽触发：在 {b_gtp} 额外长出一颗己方棋子"})

    if (game.rogue_card == "joseki_ocd"
            and not game.rogue_joseki_done):
        if (x, y) in game.rogue_joseki_targets:
            game.rogue_joseki_hits += 1
            await send_fn({"type": "rogue_event",
                           "msg": f"定式命中 ({game.rogue_joseki_hits}/{ROGUE_JOSEKI_REQUIRED_HITS})"})
        if game.rogue_joseki_hits >= ROGUE_JOSEKI_REQUIRED_HITS:
            game.rogue_joseki_done = True
            remaining_targets = [
                (tx, ty)
                for tx, ty in game.rogue_joseki_targets
                if game.board[ty][tx] != (1 if color == "B" else 2)
            ]
            changed = _set_points_to_color(game, remaining_targets, color)
            if changed and engine.ready:
                await _sync_board_to_katago(game)
            await send_fn({"type": "rogue_event",
                           "msg": f"定式强迫症完成，自动补上 {len(changed)} 颗同色棋"})

    if (game.rogue_card == "god_hand"
            and not game.rogue_godhand_done
            and (x, y) in game.rogue_godhand_trigger):
        game.rogue_godhand_done = True
        center = game.rogue_godhand_center or (x, y)
        area = _diamond_points(center[0], center[1], 2, game.size)
        enemy_first = [
            (px, py) for px, py in area
            if game.board[py][px] == (2 if color == "B" else 1)
        ]
        empty_then = [(px, py) for px, py in area if game.board[py][px] == 0]
        targets = (enemy_first + empty_then)[:ROGUE_GODHAND_FILL_COUNT]
        changed = _set_points_to_color(game, targets, color)
        if changed and engine.ready:
            await _sync_board_to_katago(game)
        await send_fn({"type": "rogue_event",
                       "msg": f"✨ 神之一手发动，在暗点周围爆发 {len(changed)} 颗同色棋"})

    if (game.rogue_card == "sansan_trap"
            and not game.rogue_sansan_trap_done
            and (x, y) in _get_sansan_points(game.size)):
        nearby = [(nx, ny) for nx, ny in _adjacent8_points(x, y, game.size) if game.board[ny][nx] == 0]
        random.shuffle(nearby)
        changed = _set_points_to_color(game, nearby[:3], color)
        if changed:
            game.rogue_sansan_trap_done = True
            if engine.ready:
                await _sync_board_to_katago(game)
            await send_fn({"type": "rogue_event",
                           "msg": f"△ 三三是陷阱发动，在 {coord_to_gtp(x, y, game.size)} 周围反打 {len(changed)} 子"})

    if game.rogue_card == "corner_helper" and not game.rogue_corner_helper_done:
        corner = _find_corner_with_min_stones(game, color, 5, 2)
        if corner is not None:
            candidates = [
                (px, py)
                for px, py in _get_corner_helper_spawn_points(game.size, corner, 5)
                if game.board[py][px] == 0
            ]
            random.shuffle(candidates)
            changed = _set_points_to_color(game, candidates[:2], color)
            if changed:
                game.rogue_corner_helper_done = True
                if engine.ready:
                    await _sync_board_to_katago(game)
                await send_fn({"type": "rogue_event",
                               "msg": f"🏯 守角辅助器补强了 {len(changed)} 颗角部援军"})

    if game.rogue_card == "sanrensei" and not game.rogue_sanrensei_done:
        player_moves = _player_non_pass_coords(game, color, limit=3)
        star_set = set(_get_star_points(game.size))
        if len(player_moves) >= 3 and all(pt in star_set for pt in player_moves[:3]):
            choices = [pt for pt in star_set if game.board[pt[1]][pt[0]] == 0]
            random.shuffle(choices)
            changed = _set_points_to_color(game, choices[:3], color)
            game.rogue_sanrensei_done = True
            if changed and engine.ready:
                await _sync_board_to_katago(game)
            await send_fn({"type": "rogue_event",
                           "msg": f"✦ 三连星发动，额外点亮 {len(changed)} 个星位"})

    if game.rogue_card == "no_regret" and random.random() < ROGUE_NO_REGRET_CHANCE:
        bonus = await _pick_second_best_point(game, color)
        if bonus:
            changed = _set_points_to_color(game, [bonus], color)
            if changed:
                if engine.ready:
                    await _sync_board_to_katago(game)
                await send_fn({"type": "rogue_event",
                               "msg": f"🚫 我不悔棋发动，在 {coord_to_gtp(bonus[0], bonus[1], game.size)} 补了一手"})

    if game.rogue_card == "foolish_wisdom":
        new_shapes = _find_new_fool_shapes(game, color, game.rogue_fool_shapes)
        changed = []
        for shape in new_shapes:
            game.rogue_fool_shapes.add(shape)
            cx, cy = _shape_center(shape)
            area = [
                (px, py)
                for px, py in _get_square_points(cx, cy, 2, game.size)
                if game.board[py][px] == 0
            ]
            random.shuffle(area)
            changed.extend(_set_points_to_color(game, area[:ROGUE_FOOLISH_FILL_COUNT], color))
        if changed and engine.ready:
            await _sync_board_to_katago(game)
        if new_shapes:
            await send_fn({"type": "rogue_event",
                           "msg": f"🪤 大智若愚发动，识别到 {len(new_shapes)} 个愚形，额外长出 {len(changed)} 颗己方棋子"})

    if (game.rogue_card == "handicap_quest"
            and game.rogue_handicap_active
            and game.rogue_handicap_bonuses < ROGUE_HANDICAP_MAX_BONUSES
            and not game.two_player):
        p_moves = sum(1 for c, m in game.moves
                      if c == game.player_color and m.upper() != "PASS")
        if (p_moves > 0
                and p_moves % ROGUE_HANDICAP_BONUS_INTERVAL == 0):
            game.rogue_skip_ai = True
            game.rogue_handicap_bonuses += 1
            await send_fn({"type": "rogue_event",
                           "msg": f"让子任务奖励触发：每满 {ROGUE_HANDICAP_BONUS_INTERVAL} 手获得一次奖励，"
                                  f"当前进度 {game.rogue_handicap_bonuses}/{ROGUE_HANDICAP_MAX_BONUSES}，AI 将虚手一次"})


async def _apply_ai_rogue_response_effects(game: GoGame, send_fn,
                                           x: int, y: int,
                                           color: str):
    if game.two_player or not game.ai_rogue_enabled:
        return
    if game.ai_rogue_card == "sansan_trap" and not game.ai_rogue_sansan_trap_done:
        coord = (x, y)
        if coord in _get_sansan_points(game.size):
            nearby = [
                (nx, ny)
                for nx, ny in _adjacent8_points(coord[0], coord[1], game.size)
                if game.board[ny][nx] == 0
            ]
            random.shuffle(nearby)
            changed = _set_points_to_color(game, nearby[:3], game.ai_color)
            if changed:
                game.ai_rogue_sansan_trap_done = True
                if engine.ready:
                    await _sync_board_to_katago(game)
                await send_fn({
                    "type": "rogue_event",
                    "msg": f"三三是陷阱发动，在 {coord_to_gtp(coord[0], coord[1], game.size)} 周围反打 {len(changed)} 子"
                })


def _sync_board_to_katago_locked(game: GoGame):
    """Reset KataGo board to match game.board using SGF loadsgf.
    Must be called while holding engine.command_lock."""
    sgf = f"(;GM[1]SZ[{game.size}]KM[{game.komi}]"
    blacks, whites = [], []
    for y in range(game.size):
        for x in range(game.size):
            if game.board[y][x] == 1:
                blacks.append(f"{chr(ord('a') + x)}{chr(ord('a') + y)}")
            elif game.board[y][x] == 2:
                whites.append(f"{chr(ord('a') + x)}{chr(ord('a') + y)}")
    if blacks:
        sgf += "AB" + "".join(f"[{p}]" for p in blacks)
    if whites:
        sgf += "AW" + "".join(f"[{p}]" for p in whites)
    sgf += ")"
    tmp = os.path.join(BASE_DIR, "_ultimate_sync.sgf")
    with open(tmp, "w") as f:
        f.write(sgf)
    engine._send_command_locked(f"loadsgf {tmp}")


async def _sync_board_to_katago(game: GoGame):
    """Reset KataGo board to match game.board (async wrapper)."""
    def _do():
        with engine.command_lock:
            _sync_board_to_katago_locked(game)
    await run_in_executor(_do)


def _ultimate_get_territory_forbidden(game: GoGame, for_color_val: int) -> set:
    """Get forbidden points for a color due to opponent's 绝对领地 card.
    for_color_val: the color (1=B,2=W) that wants to PLACE a stone."""
    forbidden = set()
    owner_val = 3 - for_color_val  # the card holder's stones
    for y in range(game.size):
        for x in range(game.size):
            if game.board[y][x] == owner_val:
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < game.size and 0 <= ny < game.size:
                            if abs(dx) + abs(dy) <= ULTIMATE_TERRITORY_RADIUS:
                                forbidden.add((nx, ny))
    return forbidden


async def _apply_ultimate_effect(game: GoGame, send_fn, x: int, y: int,
                                  color: str, card: str):
    """Apply a single ultimate card effect after a stone is placed at (x,y).
    Returns True if board was modified (needs KataGo sync)."""
    import time as _time
    rng = random.Random(_time.time_ns())
    size = game.size
    cv = 1 if color == "B" else 2
    ov = 3 - cv
    modified = False

    if card == "proliferate":
        # Spawn 5 same-color stones in 5×5 area
        candidates = []
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                nx, ny = x + dx, y + dy
                if 0 <= nx < size and 0 <= ny < size and game.board[ny][nx] == 0:
                    candidates.append((nx, ny))
        rng.shuffle(candidates)
        placed = 0
        for bx, by in candidates[:5]:
            game.board[by][bx] = cv
            placed += 1
        if placed > 0:
            modified = True
            await send_fn({"type": "rogue_event",
                           "msg": f"🦠 无限增生！生成 {placed} 颗棋子"})

    elif card == "wildgrow":
        # Pick 3 random existing stones of this color, each grows a neighbor
        own_stones = [(sx, sy) for sy in range(size) for sx in range(size)
                      if game.board[sy][sx] == cv]
        rng.shuffle(own_stones)
        grown = 0
        for sx, sy in own_stones:
            if grown >= ULTIMATE_WILDGROW_MAX_GROWTH:
                break
            adj = []
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    nx, ny = sx + dx, sy + dy
                    if 0 <= nx < size and 0 <= ny < size and game.board[ny][nx] == 0:
                        adj.append((nx, ny))
            if adj:
                bx, by = rng.choice(adj)
                game.board[by][bx] = cv
                grown += 1
                modified = True
        if grown > 0:
            await send_fn({"type": "rogue_event",
                           "msg": f"🌿 狂野生长！{grown} 颗棋子生长出新子"})

    elif card == "rejection":
        # Push all opponent stones in 3×3 away from placed stone
        pushed = 0
        destroyed = 0
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < size and 0 <= ny < size and game.board[ny][nx] == ov:
                    # Push direction: away from (x,y)
                    push_x, push_y = nx + dx, ny + dy
                    game.board[ny][nx] = 0  # remove from original
                    if (0 <= push_x < size and 0 <= push_y < size
                            and game.board[push_y][push_x] == 0):
                        game.board[push_y][push_x] = ov
                        pushed += 1
                    else:
                        destroyed += 1
                    modified = True
        if pushed + destroyed > 0:
            msg = f"💥 排异反应！"
            if pushed:
                msg += f"挤走 {pushed} 子"
            if destroyed:
                msg += f"{'，' if pushed else ''}摧毁 {destroyed} 子"
            await send_fn({"type": "rogue_event", "msg": msg})

    elif card == "shadow_clone":
        # Place at the symmetric point. If occupied, try to clone into a nearby
        # empty point around the mirror so the card still pays off more often.
        mx, my = size - 1 - x, size - 1 - y
        clone_target = None
        if game.board[my][mx] == 0:
            clone_target = (mx, my)
        else:
            nearby = []
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    nx, ny = mx + dx, my + dy
                    if 0 <= nx < size and 0 <= ny < size and game.board[ny][nx] == 0:
                        nearby.append((nx, ny))
            if nearby:
                nearby.sort(key=lambda p: abs(p[0] - mx) + abs(p[1] - my))
                clone_target = nearby[0]
        if clone_target:
            tx, ty = clone_target
            game.board[ty][tx] = cv
            modified = True
            await send_fn({"type": "rogue_event",
                           "msg": f"👥 影分身！在 {coord_to_gtp(tx, ty, size)} 出现分身"})

    elif card == "plague":
        # Convert ALL enemy stones in 3×3 area
        converted = 0
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                nx, ny = x + dx, y + dy
                if 0 <= nx < size and 0 <= ny < size and game.board[ny][nx] == ov:
                    game.board[ny][nx] = cv
                    converted += 1
                    modified = True
        if converted > 0:
            await send_fn({"type": "rogue_event",
                           "msg": f"☠️ 瘟疫蔓延！感染 {converted} 颗敌子"})

    elif card == "meteor":
        # Destroy 4 random enemy stones
        enemies = [(sx, sy) for sy in range(size) for sx in range(size)
                   if game.board[sy][sx] == ov]
        rng.shuffle(enemies)
        destroyed = 0
        for ex, ey in enemies[:ULTIMATE_METEOR_DESTROY_COUNT]:
            game.board[ey][ex] = 0
            destroyed += 1
        if destroyed > 0:
            modified = True
            await send_fn({"type": "rogue_event",
                           "msg": f"☄️ 陨石雨！摧毁 {destroyed} 颗对方棋子"})

    elif card == "quantum":
        # Place on 4 random empty points
        empties = [(sx, sy) for sy in range(size) for sx in range(size)
                   if game.board[sy][sx] == 0]
        rng.shuffle(empties)
        placed = 0
        for bx, by in empties[:ULTIMATE_QUANTUM_PLACE_COUNT]:
            game.board[by][bx] = cv
            placed += 1
        if placed > 0:
            modified = True
            await send_fn({"type": "rogue_event",
                           "msg": f"⚛️ 量子纠缠！在 {placed} 个位置出现棋子"})

    elif card == "devour":
        # Eat all opponent stones in 5×5
        eaten = 0
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                nx, ny = x + dx, y + dy
                if 0 <= nx < size and 0 <= ny < size and game.board[ny][nx] == ov:
                    game.board[ny][nx] = 0
                    eaten += 1
        if eaten > 0:
            modified = True
            await send_fn({"type": "rogue_event",
                           "msg": f"👹 吞噬之口！吃掉 {eaten} 颗对方棋子"})

    elif card == "timewarp":
        # 70% chance to undo opponent's last 2 moves
        if rng.random() < ULTIMATE_TIMEWARP_TRIGGER_CHANCE:
            opp_color = "W" if color == "B" else "B"
            erased = 0
            for i in range(len(game.moves) - 1, -1, -1):
                if erased >= 2:
                    break
                mc, mg = game.moves[i]
                if mc == opp_color and mg.upper() != "PASS":
                    coord_t = gtp_to_coord(mg, size)
                    if coord_t:
                        ox, oy = coord_t
                        if game.board[oy][ox] == (1 if mc == "B" else 2):
                            game.board[oy][ox] = 0
                            erased += 1
                            modified = True
            if erased > 0:
                await send_fn({"type": "rogue_event",
                               "msg": f"⏳ 时空裂缝！抹去对方 {erased} 手棋"})

    elif card == "blackout":
        # Cross pattern: 5 tiles horizontal + 5 tiles vertical centered on (x,y)
        destroyed = 0
        for d in range(-2, 3):
            for nx, ny in [(x + d, y), (x, y + d)]:
                if 0 <= nx < size and 0 <= ny < size and game.board[ny][nx] == ov:
                    game.board[ny][nx] = 0
                    destroyed += 1
                    modified = True
        if destroyed > 0:
            await send_fn({"type": "rogue_event",
                           "msg": f"🌋 天崩地裂！十字清除 {destroyed} 颗敌子"})

    elif card == "magnet":
        # Pull all own stones 3 steps toward (x,y), destroying enemies in path
        own_stones = [(sx, sy) for sy in range(size) for sx in range(size)
                      if game.board[sy][sx] == cv and (sx, sy) != (x, y)]
        # Sort by distance so closest move first (avoid collisions)
        own_stones.sort(key=lambda p: abs(p[0] - x) + abs(p[1] - y))
        moved = 0
        crushed = 0
        for sx, sy in own_stones:
            cx, cy = sx, sy
            for _ in range(3):
                dx_dir = (0 if cx == x else (1 if cx < x else -1))
                dy_dir = (0 if cy == y else (1 if cy < y else -1))
                if dx_dir == 0 and dy_dir == 0:
                    break
                nx, ny = cx + dx_dir, cy + dy_dir
                if not (0 <= nx < size and 0 <= ny < size):
                    break
                if game.board[ny][nx] == ov:
                    game.board[ny][nx] = 0  # crush enemy
                    crushed += 1
                if game.board[ny][nx] == 0:
                    game.board[cy][cx] = 0
                    game.board[ny][nx] = cv
                    cx, cy = nx, ny
                    modified = True
                else:
                    break  # blocked by own stone
            if (cx, cy) != (sx, sy):
                moved += 1
        if moved + crushed > 0:
            msg = f"🧲 磁力吸附！{moved} 子飞奔"
            if crushed:
                msg += f"，碾碎 {crushed} 颗敌子"
            await send_fn({"type": "rogue_event", "msg": msg})

    elif card == "necro":
        # Spawn 3 own stones on random empty + convert 2 enemy stones
        empties = [(sx, sy) for sy in range(size) for sx in range(size)
                   if game.board[sy][sx] == 0]
        rng.shuffle(empties)
        spawned = 0
        for bx, by in empties[:3]:
            game.board[by][bx] = cv
            spawned += 1
            modified = True
        enemies = [(sx, sy) for sy in range(size) for sx in range(size)
                   if game.board[sy][sx] == ov]
        rng.shuffle(enemies)
        converted = 0
        for ex, ey in enemies[:2]:
            game.board[ey][ex] = cv
            converted += 1
            modified = True
        if spawned + converted > 0:
            await send_fn({"type": "rogue_event",
                           "msg": f"💀 亡灵召唤！召唤 {spawned} 子，转化 {converted} 子"})

    elif card == "joseki_burst":
        if not game.ultimate_joseki_targets:
            game.ultimate_joseki_targets = _pick_joseki_targets(
                game.size, ULTIMATE_JOSEKI_TARGET_COUNT)
        if not game.ultimate_joseki_done and (x, y) in game.ultimate_joseki_targets:
            game.ultimate_joseki_hits += 1
            await send_fn({"type": "rogue_event",
                           "msg": f"定式爆发命中 ({game.ultimate_joseki_hits}/{ULTIMATE_JOSEKI_REQUIRED_HITS})"})
        if not game.ultimate_joseki_done and game.ultimate_joseki_hits >= ULTIMATE_JOSEKI_REQUIRED_HITS:
            game.ultimate_joseki_done = True
            remaining_targets = [
                (tx, ty)
                for tx, ty in game.ultimate_joseki_targets
                if game.board[ty][tx] != cv
            ]
            changed = _set_points_to_color(game, remaining_targets, color)
            burst_points = _collect_joseki_burst_points(
                game,
                game.ultimate_joseki_targets,
                color,
                ULTIMATE_JOSEKI_BONUS_STONES,
                rng,
            )
            changed.extend(_set_points_to_color(game, burst_points, color))
            if changed:
                modified = True
                await send_fn({"type": "rogue_event",
                               "msg": f"定式爆发完成：补满 {len(remaining_targets)} 个目标点，并额外爆发 {len(changed) - len(remaining_targets)} 颗棋子"})

    elif card == "god_hand":
        if not game.ultimate_godhand_trigger:
            game.ultimate_godhand_center = _random_hidden_center(game.size, 2, rng)
            game.ultimate_godhand_trigger = _diamond_points(
                game.ultimate_godhand_center[0],
                game.ultimate_godhand_center[1],
                2,
                game.size,
            )
        if not game.ultimate_godhand_done and (x, y) in game.ultimate_godhand_trigger:
            game.ultimate_godhand_done = True
            cleared = 0
            for sy in range(size):
                for sx in range(size):
                    if game.board[sy][sx] == ov:
                        game.board[sy][sx] = 0
                        cleared += 1
                        modified = True
            empties = [(sx, sy) for sy in range(size) for sx in range(size) if game.board[sy][sx] == 0]
            rng.shuffle(empties)
            filled = 0
            for bx, by in empties[:ULTIMATE_GODHAND_FILL_COUNT]:
                game.board[by][bx] = cv
                filled += 1
                modified = True
            await send_fn({"type": "rogue_event",
                           "msg": f"✨ 神之一手发动，清空 {cleared} 颗敌子并洒下 {filled} 颗同色棋"})

    elif card == "corner_helper":
        if not game.ultimate_corner_helper_done:
            corner = _find_corner_with_min_stones(game, color, 5, 2)
            if corner is not None:
                cleared = 0
                for px, py in _get_corner_square_points(size, corner, 8):
                    if game.board[py][px] == ov:
                        game.board[py][px] = 0
                        cleared += 1
                        modified = True
                boundary = _get_corner_boundary_points(size, corner, 8)
                placed = _set_points_to_color(game, boundary, color)
                if placed:
                    modified = True
                if cleared or placed:
                    game.ultimate_corner_helper_done = True
                    await send_fn({"type": "rogue_event",
                                   "msg": f"🏯 守角辅助器封锁角部，清空 {cleared} 子并筑边 {len(placed)} 子"})

    elif card == "sanrensei":
        if not game.ultimate_sanrensei_done:
            first_three = _player_non_pass_coords(game, color, limit=3)
            star_set = set(_get_star_points(size))
            if len(first_three) >= 3 and all(pt in star_set for pt in first_three[:3]):
                changed = []
                cleared = 0
                seen = set()
                for sx, sy in star_set:
                    for px, py in _diamond_points(sx, sy, 2, size):
                        if (px, py) in seen:
                            continue
                        seen.add((px, py))
                        if game.board[py][px] == ov:
                            game.board[py][px] = 0
                            cleared += 1
                            modified = True
                    changed.extend(_set_points_to_color(
                        game,
                        _diamond_points(sx, sy, 2, size, boundary_only=True) + [(sx, sy)],
                        color,
                    ))
                if changed:
                    modified = True
                game.ultimate_sanrensei_done = True
                await send_fn({"type": "rogue_event",
                               "msg": f"✦ 三连星爆发，清空 {cleared} 子并扩张 {len(changed)} 颗星位势力"})

    elif card == "foolish_wisdom":
        pending_shapes = _find_new_fool_shapes(game, color, game.ultimate_fool_shapes)
        wave = 0
        total_generated = 0
        while pending_shapes:
            for shape in pending_shapes:
                game.ultimate_fool_shapes.add(shape)
            empties = [
                (sx, sy)
                for sy in range(size)
                for sx in range(size)
                if game.board[sy][sx] == 0
            ]
            rng.shuffle(empties)
            batch = empties[:ULTIMATE_FOOLISH_FILL_COUNT]
            if not batch:
                break
            for bx, by in batch:
                game.board[by][bx] = cv
                modified = True
            wave += 1
            total_generated += len(batch)
            await send_fn({"type": "rogue_event",
                           "msg": f"🪤 大智若愚第 {wave} 波发动，识别到 {len(pending_shapes)} 个愚形，生成 {len(batch)} 颗己方棋子"})
            pending_shapes = _find_new_fool_shapes(game, color, game.ultimate_fool_shapes)
            if pending_shapes:
                await asyncio.sleep(ULTIMATE_FOOLISH_CHAIN_DELAY)
        if total_generated > 0:
            await send_fn({"type": "rogue_event",
                           "msg": f"🪤 大智若愚连锁结束，本次共生成 {total_generated} 颗己方棋子"})

    elif card == "wall":
        # Fill whichever of the row/column yields the larger wall so the card
        # feels explosive rather than coin-flippy.
        row_slots = sum(1 for fx in range(size) if game.board[y][fx] == 0)
        col_slots = sum(1 for fy in range(size) if game.board[fy][x] == 0)
        choose_row = row_slots >= col_slots
        if choose_row:
            placed = 0
            for fx in range(size):
                if game.board[y][fx] == 0:
                    game.board[y][fx] = cv
                    placed += 1
                    modified = True
            if placed > 0:
                await send_fn({"type": "rogue_event",
                               "msg": f"🧱 万里长城！第 {size - y} 行筑起 {placed} 子"})
        else:
            placed = 0
            for fy in range(size):
                if game.board[fy][x] == 0:
                    game.board[fy][x] = cv
                    placed += 1
                    modified = True
            if placed > 0:
                cols = "ABCDEFGHJKLMNOPQRST"
                await send_fn({"type": "rogue_event",
                               "msg": f"🧱 万里长城！{cols[x]} 列筑起 {placed} 子"})

    return modified


async def _ultimate_force_score(game: GoGame, send_fn):
    """Force game end in ultimate mode — count stones for scoring."""
    game.game_over = True
    # Simple area scoring: count stones + enclosed territory
    b_score = 0
    w_score = 0
    size = game.size
    visited = [[False] * size for _ in range(size)]

    # Count stones
    for y in range(size):
        for x in range(size):
            if game.board[y][x] == 1:
                b_score += 1
            elif game.board[y][x] == 2:
                w_score += 1

    # Flood fill for territory
    for y in range(size):
        for x in range(size):
            if game.board[y][x] == 0 and not visited[y][x]:
                # BFS
                region = []
                stack = [(x, y)]
                borders = set()
                while stack:
                    cx, cy = stack.pop()
                    if visited[cy][cx]:
                        continue
                    visited[cy][cx] = True
                    region.append((cx, cy))
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < size and 0 <= ny < size:
                            if game.board[ny][nx] == 0 and not visited[ny][nx]:
                                stack.append((nx, ny))
                            elif game.board[ny][nx] != 0:
                                borders.add(game.board[ny][nx])
                if len(borders) == 1:
                    owner = borders.pop()
                    if owner == 1:
                        b_score += len(region)
                    else:
                        w_score += len(region)

    b_score_final = b_score
    w_score_final = w_score + game.komi
    if b_score_final > w_score_final:
        winner = "B"
        score_str = f"B+{b_score_final - w_score_final:.1f}"
    else:
        winner = "W"
        score_str = f"W+{w_score_final - b_score_final:.1f}"

    game.winner = winner
    await send_fn({"type": "game_state", **game.to_state()})
    await send_fn({"type": "game_over", "winner": winner,
                    "score": score_str, "reason": "ultimate_20moves"})


async def _ultimate_ai_move(game: GoGame, send_fn,
                            allow_double_bonus: bool = True):
    """AI move in ultimate mode - generates move, applies AI's card effect."""
    if game.game_over or not engine.ready:
        return

    game.ultimate_extra_turn = False
    color = game.ai_color
    ai_card = game.ultimate_ai_card
    cv = 1 if color == "B" else 2

    forbidden = set()
    if game.ultimate_player_card == "territory":
        forbidden = _ultimate_get_territory_forbidden(game, cv)

    await _sync_board_to_katago(game)
    visits = get_game_visits(game.level, len(game.moves), mode="ultimate")

    def _gen():
        with engine.command_lock:
            engine._send_command_locked(f"kata-set-param maxVisits {visits}")
            resp = engine._send_command_locked(f"genmove {color}", timeout=30)
            engine._send_command_locked(
                f"kata-set-param maxVisits {get_game_visits(game.level, 0, mode='ultimate')}")
            return resp.replace("=", "").strip()

    gtp_move = await run_in_executor(_gen)
    if gtp_move.upper() == "RESIGN":
        gtp_move = await _ai_move_no_resign(game, color)

    if forbidden and gtp_move.upper() not in ("PASS", "RESIGN"):
        coord = gtp_to_coord(gtp_move, game.size)
        if coord and coord in forbidden:
            import time as _time
            rng = random.Random(_time.time_ns())
            valid = [(sx, sy) for sy in range(game.size) for sx in range(game.size)
                     if game.board[sy][sx] == 0 and (sx, sy) not in forbidden]
            if valid:
                bx, by = rng.choice(valid)
                gtp_move = coord_to_gtp(bx, by, game.size)
            else:
                gtp_move = "pass"

    coord = gtp_to_coord(gtp_move, game.size)
    if gtp_move.upper() != "PASS" and coord:
        x, y = coord
        if game.board[y][x] != 0:
            import time as _time
            rng = random.Random(_time.time_ns())
            empties = [(sx, sy) for sy in range(game.size) for sx in range(game.size)
                       if game.board[sy][sx] == 0]
            if empties:
                x, y = rng.choice(empties)
                gtp_move = coord_to_gtp(x, y, game.size)
                coord = (x, y)
            else:
                gtp_move = "pass"
                coord = None

    game.ultimate_move_count += 1
    game.moves.append((color, gtp_move))

    if gtp_move.upper() != "PASS" and coord:
        game.place_stone(coord[0], coord[1], color)
        game.passed[color] = False
    else:
        game.passed[color] = True

    await send_fn({"type": "ai_move", "gtp": gtp_move, "color": color,
                    "x": coord[0] if coord else None,
                    "y": coord[1] if coord else None})

    board_modified = False
    if ai_card and coord and gtp_move.upper() != "PASS":
        board_modified = await _apply_ultimate_effect(
            game, send_fn, coord[0], coord[1], color, ai_card)
        if board_modified:
            # AI-side ultimate effects can rewrite the visible board directly.
            # Sync immediately so the engine does not continue from a stale
            # pre-effect position on the player's next move.
            await _sync_board_to_katago(game)

    chain_bonus = (
        ai_card == "chain"
        and gtp_move.upper() != "PASS"
        and random.random() < ULTIMATE_CHAIN_EXTRA_TURN_CHANCE
        and not game.game_over
    )
    double_bonus = (
        ai_card == "double"
        and allow_double_bonus
        and not game.game_over
        and gtp_move.upper() != "PASS"
    )

    if chain_bonus:
        game.ultimate_extra_turn = True
        game.current_player = color
        await send_fn({"type": "rogue_event", "msg": "AI 的连珠棋触发，AI 将继续落子"})
        await send_fn({"type": "game_state", **game.to_state()})
        if game.ultimate_move_count < 20:
            await _ultimate_ai_move(game, send_fn)
            return

    if double_bonus:
        game.ultimate_extra_turn = True
        game.current_player = color
        await send_fn({"type": "rogue_event", "msg": "AI 的双刀流触发，AI 将继续落子"})
        await send_fn({"type": "game_state", **game.to_state()})
        if game.ultimate_move_count < 20:
            await _ultimate_ai_move(game, send_fn, allow_double_bonus=False)
            return

    game.ultimate_extra_turn = False
    game.current_player = game.player_color
    _prepare_player_turn_modifiers(game)
    await send_fn({"type": "game_state", **game.to_state()})

    if game.ultimate_move_count >= 20:
        await _ultimate_force_score(game, send_fn)


async def _ai_move(game: GoGame, send_fn):
    if game.game_over or not engine.ready:
        return

    color = game.ai_color
    card = game.rogue_card
    move_count = len(game.moves)
    ai_move_count = sum(1 for c, _ in game.moves if c == color)

    if card == "dice" and random.random() < ROGUE_DICE_PASS_CHANCE:
        await run_in_executor(engine.send_command, f"play {color} pass")
        game.moves.append((color, "pass"))
        game.passed[color] = True
        game.current_player = game.player_color
        _prepare_player_turn_modifiers(game)
        await send_fn({"type": "game_state", **game.to_state()})
        await send_fn({"type": "ai_move", "gtp": "pass", "color": color,
                        "x": None, "y": None})
        await send_fn({"type": "rogue_event",
                        "msg": "投骰子触发，AI 这手选择虚手"})
        return

    if card == "mirror" and random.random() < ROGUE_MIRROR_CHANCE and move_count > 0:
        last_color, last_gtp = game.moves[-1]
        if last_color == game.player_color and last_gtp.upper() != "PASS":
            lc = gtp_to_coord(last_gtp, game.size)
            if lc:
                mx, my = _mirror_coord(lc[0], lc[1], game.size)
                if game.board[my][mx] == 0:
                    m_gtp = coord_to_gtp(mx, my, game.size)
                    resp = await run_in_executor(
                        engine.send_command, f"play {color} {m_gtp}")
                    if "?" not in resp:
                        game.moves.append((color, m_gtp))
                        game.place_stone(mx, my, color)
                        game.passed[color] = False
                        game.current_player = game.player_color
                        _prepare_player_turn_modifiers(game)
                        await send_fn({"type": "game_state", **game.to_state()})
                        await send_fn({"type": "ai_move", "gtp": m_gtp,
                                        "color": color, "x": mx, "y": my})
                        await send_fn({"type": "rogue_event",
                                        "msg": f"镜像触发，AI 在对称点 {m_gtp} 落子"})
                        return

    if card == "exchange" and game.rogue_skip_ai:
        game.rogue_skip_ai = False
        await run_in_executor(engine.send_command, f"play {color} pass")
        game.moves.append((color, "pass"))
        game.passed[color] = True
        game.current_player = game.player_color
        _prepare_player_turn_modifiers(game)
        await send_fn({"type": "game_state", **game.to_state()})
        await send_fn({"type": "ai_move", "gtp": "pass", "color": color,
                        "x": None, "y": None})
        await send_fn({"type": "rogue_event",
                        "msg": "乾坤挪移生效，AI 本回合虚手并把回合交还给你"})
        return

    _mode = "rogue" if card else "normal"
    visits = get_game_visits(game.level, move_count, mode=_mode)

    if card == "nerf":
        visits = max(100, int(visits * ROGUE_NERF_FACTOR))

    if move_count < OPENING_MOVE_THRESHOLD:
        time_limit = min(3.0, MAX_MOVE_TIME)
    elif visits > 5000:
        time_limit = MAX_MOVE_TIME
    else:
        time_limit = 8.0

    if card == "time_press":
        time_limit = min(ROGUE_TIME_PRESS_MAX_TIME, time_limit)
        visits = min(visits, ROGUE_TIME_PRESS_MAX_VISITS)

    if card == "fog":
        rng = random.Random(time.time_ns())
        game.rogue_seal_points = _pick_fog_mask(game.size, rng)
        await send_fn({"type": "game_state", **game.to_state()})
        await send_fn({"type": "rogue_event",
                       "msg": "🌫 迷雾刷新：高亮 3x3 区域本回合对 AI 禁止落子"})

    if card == "tengen" and ai_move_count < 2:
        if ai_move_count == 0:
            c = game.size // 2
            target = (c, c)
            msg = "天元触发，AI 优先抢下天元"
        else:
            star_pts = _get_star_points(game.size)
            available = [(x, y) for x, y in star_pts
                         if game.board[y][x] == 0
                         and (x, y) != (game.size // 2, game.size // 2)]
            if available:
                target = random.choice(available)
                msg = "天元触发，AI 优先补下星位"
            else:
                target = None
                msg = None
        if target:
            tx, ty = target
            if game.board[ty][tx] == 0:
                t_gtp = coord_to_gtp(tx, ty, game.size)
                resp = await run_in_executor(
                    engine.send_command, f"play {color} {t_gtp}")
                if "?" not in resp:
                    game.moves.append((color, t_gtp))
                    game.place_stone(tx, ty, color)
                    game.passed[color] = False
                    game.current_player = game.player_color
                    _prepare_player_turn_modifiers(game)
                    await send_fn({"type": "game_state", **game.to_state()})
                    await send_fn({"type": "ai_move", "gtp": t_gtp,
                                    "color": color, "x": tx, "y": ty})
                    if msg:
                        await send_fn({"type": "rogue_event", "msg": msg})
                    return

    if card == "gravity" and ai_move_count < ROGUE_GRAVITY_AI_MOVES:
        star_pts = _get_star_points(game.size)
        available = [(x, y) for x, y in star_pts if game.board[y][x] == 0]
        if available:
            gtp_move = await _ai_move_avoid_points_allow_only(
                game, color, visits, time_limit, available)
            if gtp_move:
                await _finish_ai_move(game, send_fn, color, card, gtp_move,
                                      "引力触发，AI 被限制在星位附近落子")
                return

    if card == "lowline" and ai_move_count < ROGUE_LOWLINE_AI_MOVES:
        allowed = [(x, y) for x in range(game.size) for y in range(game.size)
                   if _is_lowline(x, y, game.size) and game.board[y][x] == 0]
        if allowed:
            gtp_move = await _ai_move_avoid_points_allow_only(
                game, color, visits, time_limit, allowed)
            if gtp_move:
                await _finish_ai_move(game, send_fn, color, card, gtp_move,
                                      "低空飞行触发，AI 继续在低线路落子")
                return

    if card == "sansan":
        if ai_move_count < 4:
            sansan_pts = _get_sansan_points(game.size)
            available = [(x, y) for x, y in sansan_pts if game.board[y][x] == 0]
            if available:
                gtp_move = await _ai_move_avoid_points_allow_only(
                    game, color, visits, time_limit, available)
                if gtp_move:
                    await _finish_ai_move(game, send_fn, color, card, gtp_move,
                                          "三三开局触发，AI 优先抢角三三")
                    return
        elif ai_move_count < 8:
            corner_ban = []
            for cy in (0, game.size - 5):
                for cx in (0, game.size - 5):
                    for dy in range(5):
                        for dx in range(5):
                            corner_ban.append((cx + dx, cy + dy))
            gtp_move = await _ai_move_avoid_points(
                game, color, visits, time_limit, corner_ban)
            await _finish_ai_move(game, send_fn, color, card, gtp_move,
                                  "三三开局后半段生效，AI 暂时避开角部 5x5")
            return

    if card == "shadow" and ai_move_count in ROGUE_SHADOW_AI_MOVE_INDEXES:
        prev_ai_gtp = None
        for mc, mg in reversed(game.moves):
            if mc == color and mg.upper() != "PASS":
                prev_ai_gtp = mg
                break
        if prev_ai_gtp:
            fc = gtp_to_coord(prev_ai_gtp, game.size)
            if fc:
                adj = _adjacent_points(fc[0], fc[1], game.size)
                available = [(x, y) for x, y in adj if game.board[y][x] == 0]
                if available:
                    gtp_move = await _ai_move_avoid_points_allow_only(
                        game, color, visits, time_limit, available)
                    if gtp_move:
                        await _finish_ai_move(game, send_fn, color, card,
                                              gtp_move,
                                              "影子触发，AI 贴着自己的上一手继续下")
                        return

    if card == "suboptimal" and ai_move_count < ROGUE_SUBOPTIMAL_AI_MOVES:
        gtp_move = await _ai_move_suboptimal(game, color, visits, time_limit)
        if gtp_move:
            await _finish_ai_move(game, send_fn, color, card, gtp_move,
                                  "次优之选触发，AI 采用了较弱备选点")
            return

    forbidden = []
    if card == "seal" and game.rogue_seal_points:
        forbidden = game.rogue_seal_points
    elif card == "fog" and game.rogue_seal_points:
        forbidden = game.rogue_seal_points
    elif card == "blackhole":
        forbidden = _get_blackhole_points(game.size)
    elif card == "golden_corner" and game.rogue_seal_points:
        forbidden = game.rogue_seal_points

    if forbidden:
        gtp_move = await _ai_move_avoid_points(
            game, color, visits, time_limit, forbidden)
    else:
        def _genmove_atomic():
            with engine.command_lock:
                mv = 10000000 if visits == 0 else visits
                engine._send_command_locked(f"kata-set-param maxVisits {mv}")
                engine.current_visits = visits
                engine._send_command_locked(
                    f"kata-set-param maxTime {time_limit}")
                resp = engine._send_command_locked(
                    f"genmove {color}",
                    timeout=max(60, time_limit + 15))
                engine._send_command_locked("kata-set-param maxTime -1")
                return resp

        resp = await run_in_executor(_genmove_atomic)
        if game.game_over:
            return
        if "?" in resp:
            print(f"[AI] genmove returned error: {resp}")
            return
        gtp_move = resp.replace("=", "").strip()

    if gtp_move.upper() == "RESIGN":
        if card:
            gtp_move = await _ai_move_no_resign(game, color)
        else:
            game.game_over = True
            game.winner = game.player_color
            await send_fn({"type": "game_over", "winner": game.player_color,
                            "score": None, "reason": "ai_resign"})
            return

    slip_msg = None
    needs_sync = False
    if card == "slip" and gtp_move.upper() not in {"PASS", "RESIGN"} and random.random() < ROGUE_SLIP_CHANCE:
        original_gtp = gtp_move
        original_coord = gtp_to_coord(gtp_move, game.size)
        if original_coord:
            nearby = [
                (nx, ny)
                for nx, ny in _adjacent8_points(original_coord[0], original_coord[1], game.size)
                if game.board[ny][nx] == 0
            ]
            if nearby:
                sx, sy = random.choice(nearby)
                gtp_move = coord_to_gtp(sx, sy, game.size)
                needs_sync = True
                slip_msg = f"手滑了触发，AI 原本想下 {original_gtp}，结果滑到 {gtp_move}"

    game.moves.append((color, gtp_move))

    captured = 0
    if gtp_move.upper() != "PASS":
        coord = gtp_to_coord(gtp_move, game.size)
        if coord:
            captured = game.place_stone(coord[0], coord[1], color)
        game.passed[color] = False
    else:
        coord = None
        game.passed[color] = True

    extra_board_change = False
    if card == "sansan_trap" and not game.rogue_sansan_trap_done and ai_move_count == 0 and coord in _get_sansan_points(game.size):
        player_color = game.player_color
        nearby = [(nx, ny) for nx, ny in _adjacent8_points(coord[0], coord[1], game.size) if game.board[ny][nx] == 0]
        random.shuffle(nearby)
        changed = _set_points_to_color(game, nearby[:3], player_color)
        if changed:
            game.rogue_sansan_trap_done = True
            extra_board_change = True
            await send_fn({"type": "rogue_event",
                           "msg": f"△ 三三是陷阱发动，在 {coord_to_gtp(coord[0], coord[1], game.size)} 周围反打 {len(changed)} 子"})

    if needs_sync or extra_board_change:
        await _sync_board_to_katago(game)

    game.current_player = game.player_color
    _prepare_player_turn_modifiers(game)

    if card == "erosion" and captured > 0:
        shift = 2.0 * captured
        if game.ai_color == "W":
            game.komi += shift
        else:
            game.komi -= shift
        await run_in_executor(engine.send_command, f"komi {game.komi}")
        await send_fn({"type": "rogue_event",
                        "msg": f"蚕食反制：AI 提掉了 {captured} 子，当前贴目变为 {game.komi}"})

    await send_fn({"type": "game_state", **game.to_state()})

    if game.passed["B"] and game.passed["W"]:
        resp_score = await run_in_executor(engine.send_command, "final_score")
        score_str = resp_score.replace("=", "").strip()
        winner = "B" if score_str.startswith("B") else "W"
        game.game_over = True
        game.winner = winner
        await send_fn({"type": "ai_move", "gtp": gtp_move, "color": color,
                        "x": None, "y": None})
        if slip_msg:
            await send_fn({"type": "rogue_event", "msg": slip_msg})
        await send_fn({"type": "game_over", "winner": winner,
                        "score": score_str, "reason": "double_pass"})
        return

    await send_fn({"type": "ai_move", "gtp": gtp_move, "color": color,
                    "x": coord[0] if coord else None,
                    "y": coord[1] if coord else None})
    if slip_msg:
        await send_fn({"type": "rogue_event", "msg": slip_msg})


async def _ai_move_avoid_points(game, color, visits, time_limit, forbidden):
    """Generate an AI move while avoiding forbidden points (seal card)."""
    forbidden_gtp = set()
    for x, y in forbidden:
        forbidden_gtp.add(coord_to_gtp(x, y, game.size))
    forbidden_gtp_upper = {s.upper() for s in forbidden_gtp}

    def _analyze_and_pick():
        with engine.command_lock:
            mv = 10000000 if visits == 0 else visits
            engine._send_command_locked(f"kata-set-param maxVisits {mv}")
            engine.current_visits = visits
            engine._send_command_locked(
                f"kata-set-param maxTime {time_limit}")
            # Use genmove first
            resp = engine._send_command_locked(
                f"genmove {color}", timeout=max(60, time_limit + 15))
            engine._send_command_locked("kata-set-param maxTime -1")

            gtp_move = resp.replace("=", "").strip()
            # If move is not on a forbidden point, use it
            if gtp_move.upper() in ("PASS", "RESIGN") or \
               gtp_move.upper() not in forbidden_gtp_upper:
                return gtp_move

            # Move hit a sealed point — undo and try with reduced visits
            engine._send_command_locked("undo")
            # Try a few times with randomization
            for attempt in range(5):
                v = max(50, visits // (2 + attempt))
                engine._send_command_locked(f"kata-set-param maxVisits {v}")
                resp2 = engine._send_command_locked(
                    f"genmove {color}", timeout=20)
                m = resp2.replace("=", "").strip()
                if m.upper() in ("PASS", "RESIGN") or \
                   m.upper() not in forbidden_gtp_upper:
                    return m
                engine._send_command_locked("undo")

            # Final fallback: pick any legal point outside the forbidden set
            # so cards like seal/blackhole/golden_corner always honor their
            # promise instead of occasionally leaking a forbidden move.
            allowed = [(x, y) for y in range(game.size) for x in range(game.size)
                       if game.board[y][x] == 0
                       and coord_to_gtp(x, y, game.size).upper()
                       not in forbidden_gtp_upper]
            random.shuffle(allowed)
            for ax, ay in allowed:
                gtp = coord_to_gtp(ax, ay, game.size)
                r = engine._send_command_locked(f"play {color} {gtp}")
                if "?" not in r:
                    return gtp

            # No legal points remain outside the forbidden set.
            engine._send_command_locked(f"play {color} pass")
            return "pass"

    return await run_in_executor(_analyze_and_pick)


async def _ai_move_avoid_points_allow_only(game, color, visits, time_limit,
                                           allowed: list[tuple[int, int]]):
    """Generate AI move restricted to a set of allowed coordinates.

    Uses genmove then retries if the move isn't in the allowed set.
    Falls back to random pick from allowed if KataGo keeps choosing outside.
    """
    allowed_gtp = {coord_to_gtp(x, y, game.size).upper() for x, y in allowed}

    def _pick():
        with engine.command_lock:
            mv = max(50, min(visits, 2000))  # lower visits for faster retry
            engine._send_command_locked(f"kata-set-param maxVisits {mv}")
            engine.current_visits = mv
            engine._send_command_locked(
                f"kata-set-param maxTime {min(time_limit, 3.0)}")

            for attempt in range(6):
                v = max(50, mv // (1 + attempt))
                engine._send_command_locked(f"kata-set-param maxVisits {v}")
                resp = engine._send_command_locked(
                    f"genmove {color}", timeout=15)
                m = resp.replace("=", "").strip()
                if m.upper() in ("PASS", "RESIGN"):
                    engine._send_command_locked("kata-set-param maxTime -1")
                    return m
                if m.upper() in allowed_gtp:
                    engine._send_command_locked("kata-set-param maxTime -1")
                    return m
                engine._send_command_locked("undo")

            # Fallback: pick a random allowed point
            engine._send_command_locked("kata-set-param maxTime -1")
            random.shuffle(allowed)
            for ax, ay in allowed:
                if game.board[ay][ax] == 0:
                    gtp = coord_to_gtp(ax, ay, game.size)
                    r = engine._send_command_locked(f"play {color} {gtp}")
                    if "?" not in r:
                        return gtp
            # Nothing worked, let AI play freely
            resp = engine._send_command_locked(f"genmove {color}", timeout=15)
            return resp.replace("=", "").strip()

    return await run_in_executor(_pick)


async def _ai_move_suboptimal(game, color, visits, time_limit):
    """Use kata-analyze to pick the 3rd~5th best move instead of the best."""

    def _analyze_pick():
        # analyze() takes command_lock internally, so don't hold it here
        mv = max(200, min(visits, 3000))
        lines, _ = engine.analyze(
            color, visits=mv, interval=50, duration=2.0,
            extra_args=["rootInfo", "true"])
        result = engine.parse_analysis(
            lines, [], game.size, to_move_color=color)

        top = result.get("top_moves", [])
        if len(top) < 3:
            return None

        # Pick randomly from positions 3~5 (0-indexed: 2~4)
        candidates = top[2:5]
        pick = random.choice(candidates)
        gtp = pick.get("move") or pick.get("gtp")
        if not gtp:
            return None

        # Play the chosen move in KataGo
        with engine.command_lock:
            resp = engine._send_command_locked(f"play {color} {gtp}")
            if "?" in resp:
                return None
        return gtp

    return await run_in_executor(_analyze_pick)


async def _ai_move_no_resign(game, color: str) -> str:
    """Retry genmove with low randomized visits to avoid resignation.
    Falls back to pass if AI still wants to resign."""

    def _retry():
        with engine.command_lock:
            for v in (100, 30, 10):
                engine._send_command_locked(f"kata-set-param maxVisits {v}")
                engine._send_command_locked("kata-set-param maxTime 2")
                resp = engine._send_command_locked(
                    f"genmove {color}", timeout=10)
                engine._send_command_locked("kata-set-param maxTime -1")
                m = resp.replace("=", "").strip()
                if m.upper() != "RESIGN":
                    return m
                engine._send_command_locked("undo")
            # All retries still resign → force pass
            engine._send_command_locked(f"play {color} pass")
            return "pass"

    return await run_in_executor(_retry)


async def _finish_ai_move(game, send_fn, color, card, gtp_move, rogue_msg=None):
    """Finalize a rogue-forced AI move: update game state and send messages."""
    if game.game_over:
        return

    if gtp_move.upper() == "RESIGN":
        if card:
            gtp_move = await _ai_move_no_resign(game, color)
        else:
            game.game_over = True
            game.winner = game.player_color
            await send_fn({"type": "game_over", "winner": game.player_color,
                            "score": None, "reason": "ai_resign"})
            return

    game.moves.append((color, gtp_move))
    captured = 0
    coord = gtp_to_coord(gtp_move, game.size)
    if gtp_move.upper() != "PASS":
        if coord:
            captured = game.place_stone(coord[0], coord[1], color)
        game.passed[color] = False
    else:
        game.passed[color] = True

    game.current_player = game.player_color

    # Erosion effect (applies even with other cards — only if card is erosion)
    if card == "erosion" and captured > 0:
        shift = 2.0 * captured
        if game.ai_color == "W":
            game.komi += shift
        else:
            game.komi -= shift
        await run_in_executor(engine.send_command, f"komi {game.komi}")
        await send_fn({"type": "rogue_event",
                        "msg": f"🐛 蚕食！AI 提 {captured} 子，贴目变为 {game.komi}"})

    await send_fn({"type": "game_state", **game.to_state()})

    if game.passed["B"] and game.passed["W"]:
        resp_score = await run_in_executor(engine.send_command, "final_score")
        score_str = resp_score.replace("=", "").strip()
        winner = "B" if score_str.startswith("B") else "W"
        game.game_over = True
        game.winner = winner
        await send_fn({"type": "ai_move", "gtp": gtp_move, "color": color,
                        "x": None, "y": None})
        await send_fn({"type": "game_over", "winner": winner,
                        "score": score_str, "reason": "double_pass"})
        return

    await send_fn({"type": "ai_move", "gtp": gtp_move, "color": color,
                    "x": coord[0] if coord else None,
                    "y": coord[1] if coord else None})
    if rogue_msg:
        await send_fn({"type": "rogue_event", "msg": rogue_msg})


if __name__ == "__main__":
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, reload=False)
