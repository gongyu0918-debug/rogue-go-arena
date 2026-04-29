"""Gameplay rank tables and balance constants."""

RANK_VISITS = {
    "18k": 2,
    "17k": 3,
    "16k": 5,
    "15k": 8,
    "14k": 12,
    "13k": 18,
    "12k": 28,
    "11k": 40,
    "10k": 60,
    "9k": 90,
    "8k": 130,
    "7k": 180,
    "6k": 260,
    "5k": 380,
    "4k": 550,
    "3k": 800,
    "2k": 1100,
    "1k": 1500,
    "a1d": 2200,
    "a2d": 3500,
    "a3d": 5500,
    "a4d": 9000,
    "a5d": 12000,
    "a6d": 15000,
    "a7d": 18000,
    "a8d": 20000,
    "a9d": 22000,
    "p1d": 24000,
    "p2d": 26000,
    "p3d": 28000,
    "p4d": 30000,
    "p5d": 32000,
    "p6d": 34000,
    "p7d": 36000,
    "p8d": 38000,
    "p9d": 0,
}

RANK_LABELS = {
    "18k": "18级",
    "17k": "17级",
    "16k": "16级",
    "15k": "15级",
    "14k": "14级",
    "13k": "13级",
    "12k": "12级",
    "11k": "11级",
    "10k": "10级",
    "9k": "9级",
    "8k": "8级",
    "7k": "7级",
    "6k": "6级",
    "5k": "5级",
    "4k": "4级",
    "3k": "3级",
    "2k": "2级",
    "1k": "1级",
    "a1d": "业余1段",
    "a2d": "业余2段",
    "a3d": "业余3段",
    "a4d": "业余4段",
    "a5d": "业余5段",
    "a6d": "业余6段",
    "a7d": "业余7段",
    "a8d": "业余8段",
    "a9d": "业余9段",
    "p1d": "职业一段",
    "p2d": "职业二段",
    "p3d": "职业三段",
    "p4d": "职业四段",
    "p5d": "职业五段",
    "p6d": "职业六段",
    "p7d": "职业七段",
    "p8d": "职业八段",
    "p9d": "职业九段",
}

MAX_GAME_VISITS = 20000
ROGUE_MAX_VISITS = 800
ULTIMATE_MAX_VISITS = 400
CPU_MAX_VISITS = 250

ROGUE_DICE_PASS_CHANCE = 0.10
ROGUE_SLIP_CHANCE = 0.14
ROGUE_MIRROR_CHANCE = 0.16
ROGUE_NERF_FACTOR = 0.05
ROGUE_NERF_BACKUP_CHANCE = 0.60
ROGUE_NERF_BACKUP_AI_MOVES = 12
ROGUE_EROSION_SHIFT = 4.0
ROGUE_TENGEN_AI_MOVES = 5
ROGUE_FOG_MASK_RADIUS = 1
ROGUE_FOG_AI_MOVES = 11
ROGUE_FOG_POST_MASK_POINTS = 2
ROGUE_BLACKHOLE_AI_MOVES = 6
ROGUE_GOLDEN_CORNER_AI_MOVES = 10
ROGUE_GOLDEN_CORNER_SPAN = 4
ROGUE_GRAVITY_AI_MOVES = 7
ROGUE_LOWLINE_AI_MOVES = 8
ROGUE_SHADOW_AI_MOVE_INDEXES = {1, 2, 3}
ROGUE_SHADOW_CHANCE = 0.70
ROGUE_SUBOPTIMAL_AI_MOVES = 8
ROGUE_TIME_PRESS_MAX_TIME = 0.10
ROGUE_TIME_PRESS_MAX_VISITS = 20
ROGUE_TIME_PRESS_BACKUP_CHANCE = 0.60
ROGUE_TIME_PRESS_BACKUP_AI_MOVES = 12
ROGUE_FOOLISH_FILL_COUNT = 2
ULTIMATE_FOOLISH_FILL_COUNT = 20
ULTIMATE_FOOLISH_CHAIN_DELAY = 1.0
ROGUE_HANDICAP_REQUIRED_PASSES = 1
ROGUE_HANDICAP_BONUS_INTERVAL = 8
ROGUE_HANDICAP_MAX_BONUSES = 3
ROGUE_JOSEKI_TARGET_COUNT = 7
ROGUE_JOSEKI_REQUIRED_HITS = 4
ROGUE_GODHAND_FILL_COUNT = 3
ROGUE_GODHAND_RADIUS = 1
ROGUE_CORNER_HELPER_TRIGGER_STONES = 4
ROGUE_CORNER_HELPER_STONES = 1
ROGUE_SANRENSEI_REQUIRED_STARS = 2
ROGUE_SANRENSEI_OPENING_MOVES = 2
ROGUE_SANRENSEI_BONUS_STONES = 1
ROGUE_SANRENSEI_SUPPORT_STONES = 2
ROGUE_NO_REGRET_CHANCE = 0.12
ROGUE_QUICKTHINK_FIRST_SECONDS = 4
ROGUE_QUICKTHINK_SECOND_SECONDS = 2
ROGUE_SANSAN_TRAP_STONES = 8
ROGUE_SEAL_POINT_COUNT = 4
ROGUE_FIVE_IN_ROW_SUPPORT_STONES = 4

ULTIMATE_CHAIN_EXTRA_TURN_CHANCE = 0.65
ULTIMATE_WILDGROW_MAX_GROWTH = 4
ULTIMATE_METEOR_DESTROY_COUNT = 5
ULTIMATE_QUANTUM_PLACE_COUNT = 5
ULTIMATE_TIMEWARP_TRIGGER_CHANCE = 0.85
ULTIMATE_TERRITORY_RADIUS = 4
ULTIMATE_JOSEKI_TARGET_COUNT = 7
ULTIMATE_JOSEKI_REQUIRED_HITS = 3
ULTIMATE_JOSEKI_BONUS_STONES = 50
ULTIMATE_GODHAND_FILL_COUNT = 50
ULTIMATE_QUICKTHINK_SECONDS = 5
ULTIMATE_WALL_TRIGGER_CHANCE = 0.60
ROGUE_LAST_STAND_THRESHOLD = 0.26
ULTIMATE_LAST_STAND_THRESHOLD = 0.30
ROGUE_LAST_STAND_CLEAR_COUNT = 1
ROGUE_LAST_STAND_SPAWN_COUNT = 1
ULTIMATE_LAST_STAND_CLEAR_COUNT = 30
ULTIMATE_LAST_STAND_SPAWN_COUNT = 30
ULTIMATE_FIVE_IN_ROW_CLEAR_COUNT = 30
ULTIMATE_FIVE_IN_ROW_SPAWN_COUNT = 30

MAX_MOVE_TIME = 12.0
OPENING_MOVE_THRESHOLD = 50
OPENING_MAX_VISITS = 500
AI_STYLE_OPTIONS = {"balanced", "territory", "influence", "attack", "defense"}

ROGUE_CAPTURE_FOUL_BASE = 1.00
ROGUE_CAPTURE_FOUL_STEP = 0.00
ROGUE_CAPTURE_FOUL_THRESHOLD = 4
ROGUE_CAPTURE_FOUL_KOMI_PENALTY = 4.0
ULTIMATE_CAPTURE_FOUL_THRESHOLD = 5
ULTIMATE_CAPTURE_FOUL_SCORE_PENALTY = 50.0
ROGUE_COACH_BASE_TURNS = 30
ROGUE_COACH_BONUS_TURNS = 10
ROGUE_COACH_BONUS_THRESHOLD = 0.50
ROGUE_COACH_VISITS = 20000

CHALLENGE_STAGE_BIAS_WEIGHT = 2.6
CHALLENGE_SET_MIN_COUNT = 2
CHALLENGE_DERIVATIVE_BONUS_CHANCE = 0.50
CHALLENGE_TRAP_EXTRA_TURN_CHANCE = 1.0
CHALLENGE_ZONE_EXPAND_RADIUS = 1
CHALLENGE_RESTRICTION_DECAY_CHANCE = 0.05
CHALLENGE_ACTIVE_USE_BONUS = 1


BALANCE_TUNABLES = {
    "ROGUE_MAX_VISITS": {"group": "Engine", "card": "", "label": "Rogue 搜索上限", "min": 50, "max": 5000, "step": 50},
    "ULTIMATE_MAX_VISITS": {"group": "Engine", "card": "", "label": "Ultimate 搜索上限", "min": 50, "max": 5000, "step": 50},
    "CPU_MAX_VISITS": {"group": "Engine", "card": "", "label": "CPU 搜索上限", "min": 20, "max": 2000, "step": 10},
    "ROGUE_DICE_PASS_CHANCE": {"group": "Rogue", "card": "dice", "label": "掷骰虚手概率", "min": 0, "max": 1, "step": 0.01},
    "ROGUE_SLIP_CHANCE": {"group": "Rogue", "card": "slip", "label": "手滑偏移概率", "min": 0, "max": 1, "step": 0.01},
    "ROGUE_MIRROR_CHANCE": {"group": "Rogue", "card": "mirror", "label": "镜像触发概率", "min": 0, "max": 1, "step": 0.01},
    "ROGUE_NERF_FACTOR": {"group": "Rogue", "card": "nerf", "label": "弱化搜索倍率", "min": 0.01, "max": 1, "step": 0.01},
    "ROGUE_NERF_BACKUP_CHANCE": {"group": "Rogue", "card": "nerf", "label": "弱化误选概率", "min": 0, "max": 1, "step": 0.01},
    "ROGUE_NERF_BACKUP_AI_MOVES": {"group": "Rogue", "card": "nerf", "label": "弱化影响手数", "min": 1, "max": 80, "step": 1},
    "ROGUE_EROSION_SHIFT": {"group": "Rogue", "card": "erosion", "label": "蚕食贴目偏移", "min": 0, "max": 20, "step": 0.5},
    "ROGUE_TENGEN_AI_MOVES": {"group": "Rogue", "card": "tengen", "label": "天元牵引手数", "min": 1, "max": 40, "step": 1},
    "ROGUE_FOG_MASK_RADIUS": {"group": "Rogue", "card": "fog", "label": "战争迷雾半径", "min": 0, "max": 4, "step": 1},
    "ROGUE_FOG_AI_MOVES": {"group": "Rogue", "card": "fog", "label": "战争迷雾前期手数", "min": 1, "max": 80, "step": 1},
    "ROGUE_FOG_POST_MASK_POINTS": {"group": "Rogue", "card": "fog", "label": "战争迷雾后期禁点", "min": 0, "max": 12, "step": 1},
    "ROGUE_BLACKHOLE_AI_MOVES": {"group": "Rogue", "card": "blackhole", "label": "黑洞禁入手数", "min": 1, "max": 80, "step": 1},
    "ROGUE_GOLDEN_CORNER_AI_MOVES": {"group": "Rogue", "card": "golden_corner", "label": "黄金角禁入手数", "min": 1, "max": 80, "step": 1},
    "ROGUE_GOLDEN_CORNER_SPAN": {"group": "Rogue", "card": "golden_corner", "label": "黄金角封锁宽度", "min": 1, "max": 9, "step": 1},
    "ROGUE_GRAVITY_AI_MOVES": {"group": "Rogue", "card": "gravity", "label": "星位引力手数", "min": 1, "max": 80, "step": 1},
    "ROGUE_LOWLINE_AI_MOVES": {"group": "Rogue", "card": "lowline", "label": "低空飞行手数", "min": 1, "max": 80, "step": 1},
    "ROGUE_SHADOW_CHANCE": {"group": "Rogue", "card": "shadow", "label": "影子跟手概率", "min": 0, "max": 1, "step": 0.01},
    "ROGUE_SUBOPTIMAL_AI_MOVES": {"group": "Rogue", "card": "suboptimal", "label": "次优之选手数", "min": 1, "max": 80, "step": 1},
    "ROGUE_TIME_PRESS_MAX_TIME": {"group": "Rogue", "card": "time_press", "label": "限时压制秒数", "min": 0.01, "max": 5, "step": 0.01},
    "ROGUE_TIME_PRESS_MAX_VISITS": {"group": "Rogue", "card": "time_press", "label": "限时压制访问数", "min": 1, "max": 1000, "step": 1},
    "ROGUE_TIME_PRESS_BACKUP_CHANCE": {"group": "Rogue", "card": "time_press", "label": "限时误选概率", "min": 0, "max": 1, "step": 0.01},
    "ROGUE_TIME_PRESS_BACKUP_AI_MOVES": {"group": "Rogue", "card": "time_press", "label": "限时误选手数", "min": 1, "max": 80, "step": 1},
    "ROGUE_FOOLISH_FILL_COUNT": {"group": "Rogue", "card": "foolish_wisdom", "label": "大智若愚补子", "min": 0, "max": 20, "step": 1},
    "ROGUE_HANDICAP_REQUIRED_PASSES": {"group": "Rogue", "card": "handicap_quest", "label": "让子任务虚手", "min": 0, "max": 10, "step": 1},
    "ROGUE_HANDICAP_BONUS_INTERVAL": {"group": "Rogue", "card": "handicap_quest", "label": "让子任务间隔", "min": 1, "max": 50, "step": 1},
    "ROGUE_HANDICAP_MAX_BONUSES": {"group": "Rogue", "card": "handicap_quest", "label": "让子任务奖励次数", "min": 0, "max": 20, "step": 1},
    "ROGUE_JOSEKI_TARGET_COUNT": {"group": "Rogue", "card": "joseki_ocd", "label": "定式目标数", "min": 1, "max": 30, "step": 1},
    "ROGUE_JOSEKI_REQUIRED_HITS": {"group": "Rogue", "card": "joseki_ocd", "label": "定式命中数", "min": 1, "max": 30, "step": 1},
    "ROGUE_GODHAND_FILL_COUNT": {"group": "Rogue", "card": "god_hand", "label": "神之一手补子", "min": 0, "max": 30, "step": 1},
    "ROGUE_GODHAND_RADIUS": {"group": "Rogue", "card": "god_hand", "label": "神之一手半径", "min": 0, "max": 5, "step": 1},
    "ROGUE_CORNER_HELPER_TRIGGER_STONES": {"group": "Rogue", "card": "corner_helper", "label": "守角触发子数", "min": 1, "max": 20, "step": 1},
    "ROGUE_CORNER_HELPER_STONES": {"group": "Rogue", "card": "corner_helper", "label": "守角援军子数", "min": 0, "max": 20, "step": 1},
    "ROGUE_SANRENSEI_REQUIRED_STARS": {"group": "Rogue", "card": "sanrensei", "label": "三连星所需星位", "min": 1, "max": 9, "step": 1},
    "ROGUE_SANRENSEI_OPENING_MOVES": {"group": "Rogue", "card": "sanrensei", "label": "三连星开局窗口", "min": 1, "max": 20, "step": 1},
    "ROGUE_SANRENSEI_BONUS_STONES": {"group": "Rogue", "card": "sanrensei", "label": "三连星补星位", "min": 0, "max": 10, "step": 1},
    "ROGUE_SANRENSEI_SUPPORT_STONES": {"group": "Rogue", "card": "sanrensei", "label": "三连星援军", "min": 0, "max": 20, "step": 1},
    "ROGUE_NO_REGRET_CHANCE": {"group": "Rogue", "card": "no_regret", "label": "永不悔棋白送概率", "min": 0, "max": 1, "step": 0.01},
    "ROGUE_QUICKTHINK_FIRST_SECONDS": {"group": "Rogue", "card": "quickthink", "label": "快速思考首段秒数", "min": 1, "max": 30, "step": 1},
    "ROGUE_QUICKTHINK_SECOND_SECONDS": {"group": "Rogue", "card": "quickthink", "label": "快速思考连击秒数", "min": 1, "max": 30, "step": 1},
    "ROGUE_SANSAN_TRAP_STONES": {"group": "Rogue", "card": "sansan_trap", "label": "三三陷阱反生子", "min": 0, "max": 40, "step": 1},
    "ROGUE_SEAL_POINT_COUNT": {"group": "Rogue", "card": "seal", "label": "封印点数量", "min": 1, "max": 20, "step": 1},
    "ROGUE_FIVE_IN_ROW_SUPPORT_STONES": {"group": "Rogue", "card": "five_in_row", "label": "五子连珠援军", "min": 0, "max": 30, "step": 1},
    "ROGUE_CAPTURE_FOUL_THRESHOLD": {"group": "Rogue", "card": "capture_foul", "label": "提子犯规阈值", "min": 1, "max": 50, "step": 1},
    "ROGUE_CAPTURE_FOUL_KOMI_PENALTY": {"group": "Rogue", "card": "capture_foul", "label": "提子犯规罚目", "min": 0, "max": 50, "step": 0.5},
    "ROGUE_COACH_BASE_TURNS": {"group": "Rogue", "card": "coach_mode", "label": "代练基础手数", "min": 1, "max": 120, "step": 1},
    "ROGUE_COACH_BONUS_TURNS": {"group": "Rogue", "card": "coach_mode", "label": "代练追加手数", "min": 0, "max": 120, "step": 1},
    "ROGUE_COACH_BONUS_THRESHOLD": {"group": "Rogue", "card": "coach_mode", "label": "代练追加阈值", "min": 0, "max": 1, "step": 0.01},
    "ROGUE_COACH_VISITS": {"group": "Rogue", "card": "coach_mode", "label": "代练访问数", "min": 100, "max": 50000, "step": 100},
    "ROGUE_LAST_STAND_THRESHOLD": {"group": "Rogue", "card": "last_stand", "label": "起死回生胜率阈值", "min": 0, "max": 1, "step": 0.01},
    "ROGUE_LAST_STAND_CLEAR_COUNT": {"group": "Rogue", "card": "last_stand", "label": "起死回生清子", "min": 0, "max": 30, "step": 1},
    "ROGUE_LAST_STAND_SPAWN_COUNT": {"group": "Rogue", "card": "last_stand", "label": "起死回生补子", "min": 0, "max": 30, "step": 1},
    "ULTIMATE_CHAIN_EXTRA_TURN_CHANCE": {"group": "Ultimate", "card": "chain", "label": "连珠棋追加概率", "min": 0, "max": 1, "step": 0.01},
    "ULTIMATE_WILDGROW_MAX_GROWTH": {"group": "Ultimate", "card": "wildgrow", "label": "狂野生长扩张数", "min": 0, "max": 30, "step": 1},
    "ULTIMATE_METEOR_DESTROY_COUNT": {"group": "Ultimate", "card": "meteor", "label": "陨石雨摧毁数", "min": 0, "max": 80, "step": 1},
    "ULTIMATE_QUANTUM_PLACE_COUNT": {"group": "Ultimate", "card": "quantum", "label": "量子纠缠落子数", "min": 0, "max": 80, "step": 1},
    "ULTIMATE_TIMEWARP_TRIGGER_CHANCE": {"group": "Ultimate", "card": "timewarp", "label": "时空裂缝概率", "min": 0, "max": 1, "step": 0.01},
    "ULTIMATE_TERRITORY_RADIUS": {"group": "Ultimate", "card": "territory", "label": "绝对领地半径", "min": 1, "max": 10, "step": 1},
    "ULTIMATE_JOSEKI_TARGET_COUNT": {"group": "Ultimate", "card": "joseki_burst", "label": "定式爆发目标数", "min": 1, "max": 30, "step": 1},
    "ULTIMATE_JOSEKI_REQUIRED_HITS": {"group": "Ultimate", "card": "joseki_burst", "label": "定式爆发命中数", "min": 1, "max": 30, "step": 1},
    "ULTIMATE_JOSEKI_BONUS_STONES": {"group": "Ultimate", "card": "joseki_burst", "label": "定式爆发补子", "min": 0, "max": 160, "step": 1},
    "ULTIMATE_GODHAND_FILL_COUNT": {"group": "Ultimate", "card": "god_hand", "label": "神之一手铺子", "min": 0, "max": 160, "step": 1},
    "ULTIMATE_QUICKTHINK_SECONDS": {"group": "Ultimate", "card": "quickthink", "label": "极速风暴秒数", "min": 1, "max": 30, "step": 1},
    "ULTIMATE_WALL_TRIGGER_CHANCE": {"group": "Ultimate", "card": "wall", "label": "万里长城概率", "min": 0, "max": 1, "step": 0.01},
    "ULTIMATE_CAPTURE_FOUL_THRESHOLD": {"group": "Ultimate", "card": "capture_foul", "label": "提子犯规阈值", "min": 1, "max": 80, "step": 1},
    "ULTIMATE_CAPTURE_FOUL_SCORE_PENALTY": {"group": "Ultimate", "card": "capture_foul", "label": "提子犯规罚目", "min": 0, "max": 200, "step": 1},
    "ULTIMATE_LAST_STAND_THRESHOLD": {"group": "Ultimate", "card": "last_stand", "label": "起死回生胜率阈值", "min": 0, "max": 1, "step": 0.01},
    "ULTIMATE_LAST_STAND_CLEAR_COUNT": {"group": "Ultimate", "card": "last_stand", "label": "起死回生清子", "min": 0, "max": 160, "step": 1},
    "ULTIMATE_LAST_STAND_SPAWN_COUNT": {"group": "Ultimate", "card": "last_stand", "label": "起死回生补子", "min": 0, "max": 160, "step": 1},
    "ULTIMATE_FIVE_IN_ROW_CLEAR_COUNT": {"group": "Ultimate", "card": "five_in_row", "label": "五子连珠清子", "min": 0, "max": 160, "step": 1},
    "ULTIMATE_FIVE_IN_ROW_SPAWN_COUNT": {"group": "Ultimate", "card": "five_in_row", "label": "五子连珠补子", "min": 0, "max": 160, "step": 1},
    "CHALLENGE_STAGE_BIAS_WEIGHT": {"group": "Challenge", "card": "", "label": "闯关阶段权重", "min": 0, "max": 10, "step": 0.1},
    "CHALLENGE_SET_MIN_COUNT": {"group": "Challenge", "card": "", "label": "闯关套组保底", "min": 0, "max": 10, "step": 1},
    "CHALLENGE_DERIVATIVE_BONUS_CHANCE": {"group": "Challenge", "card": "", "label": "闯关衍生奖励概率", "min": 0, "max": 1, "step": 0.01},
    "CHALLENGE_TRAP_EXTRA_TURN_CHANCE": {"group": "Challenge", "card": "", "label": "闯关陷阱追加概率", "min": 0, "max": 1, "step": 0.01},
    "CHALLENGE_ZONE_EXPAND_RADIUS": {"group": "Challenge", "card": "", "label": "闯关区域扩张半径", "min": 0, "max": 5, "step": 1},
    "CHALLENGE_RESTRICTION_DECAY_CHANCE": {"group": "Challenge", "card": "", "label": "闯关限制衰减概率", "min": 0, "max": 1, "step": 0.01},
    "CHALLENGE_ACTIVE_USE_BONUS": {"group": "Challenge", "card": "", "label": "闯关主动次数奖励", "min": 0, "max": 10, "step": 1},
}

BALANCE_DEFAULTS = {key: globals()[key] for key in BALANCE_TUNABLES}
BALANCE_OVERRIDE_ERRORS: list[str] = []


def _coerce_balance_value(key: str, value):
    default = BALANCE_DEFAULTS[key]
    if isinstance(default, int) and not isinstance(default, bool):
        if isinstance(value, str) and value.strip() == "":
            raise ValueError("empty value")
        if isinstance(value, float) and not value.is_integer():
            raise ValueError("integer value required")
        return int(value)
    if isinstance(default, float):
        if isinstance(value, str) and value.strip() == "":
            raise ValueError("empty value")
        return float(value)
    raise ValueError(f"unsupported default type: {type(default).__name__}")


def _spec_for_key(key: str, specs: dict | None = None) -> dict:
    if specs and isinstance(specs.get(key), dict):
        merged = {**BALANCE_TUNABLES[key], **specs[key]}
        if "label" in specs[key]:
            merged["label"] = specs[key]["label"]
        return merged
    return BALANCE_TUNABLES[key]


def validate_balance_values(
    values: dict,
    specs: dict | None = None,
    *,
    drop_defaults: bool = False,
) -> tuple[dict, list[str]]:
    clean: dict[str, int | float] = {}
    errors: list[str] = []
    if not isinstance(values, dict):
        return clean, ["values must be an object"]
    for key, raw_value in values.items():
        if key not in BALANCE_DEFAULTS:
            errors.append(f"{key}: unknown tunable")
            continue
        meta = _spec_for_key(key, specs)
        try:
            value = _coerce_balance_value(key, raw_value)
        except Exception as exc:
            errors.append(f"{key}: {exc}")
            continue
        min_value = meta.get("min")
        max_value = meta.get("max")
        if min_value is not None and value < min_value:
            errors.append(f"{key}: below minimum {min_value}")
            continue
        if max_value is not None and value > max_value:
            errors.append(f"{key}: above maximum {max_value}")
            continue
        if not drop_defaults or value != BALANCE_DEFAULTS[key]:
            clean[key] = value
    return clean, errors


def apply_balance_values(values: dict, specs: dict | None = None) -> list[str]:
    clean, errors = validate_balance_values(values, specs)
    if errors:
        return errors
    for key, value in clean.items():
        globals()[key] = value
    return []


def get_balance_editor_payload() -> dict:
    from app.data.cards import get_card_config_paths, get_gameplay_tuning_specs, get_gameplay_tuning_values

    specs = get_gameplay_tuning_specs()
    values = get_gameplay_tuning_values()
    clean, errors = validate_balance_values(values, specs)
    tunables = []
    for key, meta in BALANCE_TUNABLES.items():
        spec = _spec_for_key(key, specs)
        default = BALANCE_DEFAULTS[key]
        saved = clean.get(key, default)
        active = globals()[key]
        value_type = "int" if isinstance(default, int) and not isinstance(default, bool) else "float"
        tunables.append({
            "key": key,
            "label": spec.get("label", meta["label"]),
            "group": spec.get("group", meta["group"]),
            "card": spec.get("card", meta.get("card", "")),
            "type": value_type,
            "default": default,
            "active": active,
            "saved": saved,
            "next": saved,
            "min": spec.get("min"),
            "max": spec.get("max"),
            "step": spec.get("step", 1),
            "dirty": saved != default,
            "pending_restart": saved != active,
        })
    return {
        "version": 1,
        "override_path": get_card_config_paths()["user"],
        "requires_restart": False,
        "errors": errors,
        "startup_errors": list(BALANCE_OVERRIDE_ERRORS),
        "tunables": tunables,
    }


def save_balance_overrides(values: dict) -> dict:
    from app.data.cards import export_active_card_config, save_card_config

    clean, errors = validate_balance_values(values, drop_defaults=False)
    if errors:
        return {"ok": False, "errors": errors, "payload": get_balance_editor_payload()}
    config = export_active_card_config()
    for key, value in clean.items():
        if key in config.get("tuning", {}):
            config["tuning"][key]["value"] = value
    result = save_card_config(config)
    if result.get("ok"):
        apply_balance_values(clean)
    return {"ok": result.get("ok", False), "errors": result.get("errors", []), "payload": get_balance_editor_payload()}


def reset_balance_overrides() -> dict:
    from app.data.cards import get_gameplay_tuning_specs, get_gameplay_tuning_values, reset_card_config

    result = reset_card_config()
    if result.get("ok"):
        apply_balance_values(get_gameplay_tuning_values(), get_gameplay_tuning_specs())
    return {"ok": result.get("ok", False), "errors": result.get("errors", []), "payload": get_balance_editor_payload()}
