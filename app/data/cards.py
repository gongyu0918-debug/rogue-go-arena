"""Data-driven card catalog and balance configuration."""

from __future__ import annotations

import copy
import json
import os
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SUPPORTED_LOCALES = ("zh-CN", "en-US", "ja-JP", "ko-KR")
CARD_REQUIRED_FIELDS = ("name", "desc", "icon")
CHALLENGE_CATEGORIES = ("derivative", "trap", "zone", "restriction", "active")

CARD_CONFIG_BASE_PATH = Path(__file__).with_name("cards.json")
CARD_CONFIG_SCHEMA_PATH = Path(__file__).with_name("cards.schema.json")


def _local_card_config_path() -> Path:
    explicit = os.environ.get("ROGUE_GO_CARD_CONFIG")
    if explicit:
        return Path(explicit)
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "GoAI" / "cards.json"
    return Path.home() / ".rogue-go-arena" / "cards.json"


CARD_CONFIG_USER_PATH = _local_card_config_path()
CARD_CONFIG_SOURCE_PATH = CARD_CONFIG_BASE_PATH
CARD_CONFIG_ERRORS: list[str] = []
ACTIVE_CARD_CONFIG: dict[str, Any] = {}

ROGUE_CARDS: dict[str, dict[str, Any]] = {}
ULTIMATE_CARDS: dict[str, dict[str, Any]] = {}
ROGUE_FEATURED_CARDS: set[str] = set()
ULTIMATE_FEATURED_CARDS: set[str] = set()
CHALLENGE_BETA_POOL: list[str] = []
CHALLENGE_BETA_HANDICAPS: dict[int, int] = {}
CHALLENGE_CATEGORY_MAP: dict[str, str] = {}
TWO_PLAYER_ROGUE_POOL: list[str] = []
AI_ROGUE_POOL: list[str] = []
AI_ULTIMATE_POOL: list[str] = []
ROGUE_CARD_META: dict[str, dict[str, str]] = {}
ULTIMATE_CARD_META: dict[str, dict[str, str]] = {}
DEFAULT_ROGUE_META = {"tier": "B", "category": "规则改写", "complexity": "中"}
DEFAULT_ULTIMATE_META = {"tier": "S", "category": "大招", "complexity": "中"}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("config root must be an object")
    return data


def _active_config_path() -> Path:
    return CARD_CONFIG_USER_PATH if CARD_CONFIG_USER_PATH.exists() else CARD_CONFIG_BASE_PATH


def _localized_map(value: Any, field: str, card_ref: str, errors: list[str]) -> dict[str, str]:
    if isinstance(value, str):
        value = {"zh-CN": value}
    if not isinstance(value, dict):
        errors.append(f"{card_ref}: {field} must be a localized object")
        return {}
    clean: dict[str, str] = {}
    for locale, text in value.items():
        if not isinstance(locale, str) or not locale:
            errors.append(f"{card_ref}: {field} has invalid locale key")
            continue
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{card_ref}: {field}.{locale} must be non-empty text")
            continue
        clean[locale] = text
    if not clean:
        errors.append(f"{card_ref}: {field} has no usable text")
    return clean


def _localized_value(value: Any, locale: str = "zh-CN") -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    for key in (locale, "zh-CN", "en-US", "ja-JP", "ko-KR"):
        item = value.get(key)
        if isinstance(item, str) and item:
            return item
    for item in value.values():
        if isinstance(item, str) and item:
            return item
    return ""


def _runtime_card(card: dict[str, Any], locale: str = "zh-CN") -> dict[str, Any]:
    runtime = {
        key: copy.deepcopy(value)
        for key, value in card.items()
        if key not in {"name", "desc"}
    }
    runtime["name"] = _localized_value(card.get("name"), locale)
    runtime["desc"] = _localized_value(card.get("desc"), locale)
    return runtime


def _card_i18n(card: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {
        "name": copy.deepcopy(card.get("name", {})) if isinstance(card.get("name"), dict) else {"zh-CN": str(card.get("name", ""))},
        "desc": copy.deepcopy(card.get("desc", {})) if isinstance(card.get("desc"), dict) else {"zh-CN": str(card.get("desc", ""))},
    }


def _validate_card_map(config: dict[str, Any], mode: str, errors: list[str]) -> None:
    cards = config.get("cards", {}).get(mode)
    if not isinstance(cards, dict) or not cards:
        errors.append(f"cards.{mode} must be a non-empty object")
        return
    for card_id, card in cards.items():
        ref = f"cards.{mode}.{card_id}"
        if not isinstance(card_id, str) or not card_id:
            errors.append(f"{ref}: card id must be non-empty text")
            continue
        if not isinstance(card, dict):
            errors.append(f"{ref}: card must be an object")
            continue
        for field in CARD_REQUIRED_FIELDS:
            if field not in card:
                errors.append(f"{ref}: missing {field}")
        _localized_map(card.get("name"), "name", ref, errors)
        _localized_map(card.get("desc"), "desc", ref, errors)
        if not isinstance(card.get("icon"), str) or not card.get("icon"):
            errors.append(f"{ref}: icon must be non-empty text")
        uses = card.get("uses")
        if uses is not None and (not isinstance(uses, int) or isinstance(uses, bool) or uses < 0):
            errors.append(f"{ref}: uses must be a non-negative integer")


def _validate_pool(name: str, pool: Any, catalog: dict[str, Any], errors: list[str]) -> None:
    if not isinstance(pool, list):
        errors.append(f"pools.{name} must be a list")
        return
    seen: set[str] = set()
    for card_id in pool:
        if not isinstance(card_id, str):
            errors.append(f"pools.{name}: card id must be text")
            continue
        if card_id in seen:
            errors.append(f"pools.{name}: duplicated card {card_id}")
        seen.add(card_id)
        if card_id not in catalog:
            errors.append(f"pools.{name}: unknown card {card_id}")


def _validate_meta_map(name: str, meta: Any, catalog: dict[str, Any], errors: list[str]) -> None:
    if meta is None:
        return
    if not isinstance(meta, dict):
        errors.append(f"meta.{name} must be an object")
        return
    for card_id, values in meta.items():
        if card_id not in catalog:
            errors.append(f"meta.{name}: unknown card {card_id}")
        if not isinstance(values, dict):
            errors.append(f"meta.{name}.{card_id} must be an object")
            continue
        for key in ("tier", "category", "complexity"):
            if key in values and not isinstance(values[key], str):
                errors.append(f"meta.{name}.{card_id}.{key} must be text")


def _validate_tuning(config: dict[str, Any], errors: list[str]) -> None:
    tuning = config.get("tuning")
    if not isinstance(tuning, dict):
        errors.append("tuning must be an object")
        return
    for key, spec in tuning.items():
        ref = f"tuning.{key}"
        if not isinstance(spec, dict):
            errors.append(f"{ref} must be an object")
            continue
        if not isinstance(spec.get("group"), str) or not spec.get("group"):
            errors.append(f"{ref}.group must be non-empty text")
        _localized_map(spec.get("label"), "label", ref, errors)
        value = spec.get("value")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{ref}.value must be a number")
            continue
        min_value = spec.get("min")
        max_value = spec.get("max")
        step = spec.get("step", 1)
        if min_value is not None and not isinstance(min_value, (int, float)):
            errors.append(f"{ref}.min must be a number or null")
        if max_value is not None and not isinstance(max_value, (int, float)):
            errors.append(f"{ref}.max must be a number or null")
        if isinstance(min_value, (int, float)) and value < min_value:
            errors.append(f"{ref}.value is below minimum {min_value}")
        if isinstance(max_value, (int, float)) and value > max_value:
            errors.append(f"{ref}.value is above maximum {max_value}")
        if not isinstance(step, (int, float)) or isinstance(step, bool) or step <= 0:
            errors.append(f"{ref}.step must be a positive number")


def validate_card_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(config, dict):
        return ["config root must be an object"]
    if not isinstance(config.get("version"), int) or config.get("version", 0) < 1:
        errors.append("version must be a positive integer")
    locales = config.get("locales")
    if not isinstance(locales, list) or not locales:
        errors.append("locales must be a non-empty list")
    else:
        for locale in SUPPORTED_LOCALES:
            if locale not in locales:
                errors.append(f"locales must include {locale}")
    cards_root = config.get("cards")
    if not isinstance(cards_root, dict):
        errors.append("cards must be an object")
        return errors
    _validate_card_map(config, "rogue", errors)
    _validate_card_map(config, "ultimate", errors)

    rogue_cards = cards_root.get("rogue", {}) if isinstance(cards_root.get("rogue"), dict) else {}
    ultimate_cards = cards_root.get("ultimate", {}) if isinstance(cards_root.get("ultimate"), dict) else {}
    pools = config.get("pools", {})
    if not isinstance(pools, dict):
        errors.append("pools must be an object")
        pools = {}
    _validate_pool("rogue_featured", pools.get("rogue_featured", []), rogue_cards, errors)
    _validate_pool("ultimate_featured", pools.get("ultimate_featured", []), ultimate_cards, errors)
    _validate_pool("challenge_beta", pools.get("challenge_beta", []), rogue_cards, errors)
    _validate_pool("two_player_rogue", pools.get("two_player_rogue", []), rogue_cards, errors)
    _validate_pool("ai_rogue", pools.get("ai_rogue", []), rogue_cards, errors)
    _validate_pool("ai_ultimate", pools.get("ai_ultimate", []), ultimate_cards, errors)

    meta = config.get("meta", {})
    if not isinstance(meta, dict):
        errors.append("meta must be an object")
        meta = {}
    _validate_meta_map("rogue", meta.get("rogue"), rogue_cards, errors)
    _validate_meta_map("ultimate", meta.get("ultimate"), ultimate_cards, errors)

    challenge = config.get("challenge", {})
    if not isinstance(challenge, dict):
        errors.append("challenge must be an object")
        challenge = {}
    categories = challenge.get("categories", {})
    allowed_categories = challenge.get("allowed_categories", list(CHALLENGE_CATEGORIES))
    if not isinstance(allowed_categories, list) or not all(isinstance(item, str) for item in allowed_categories):
        errors.append("challenge.allowed_categories must be a text list")
        allowed_categories = list(CHALLENGE_CATEGORIES)
    if not isinstance(categories, dict):
        errors.append("challenge.categories must be an object")
    else:
        for card_id, category in categories.items():
            if card_id not in rogue_cards:
                errors.append(f"challenge.categories: unknown card {card_id}")
            if category not in allowed_categories:
                errors.append(f"challenge.categories.{card_id}: unknown category {category}")
    handicaps = challenge.get("handicaps", {})
    if not isinstance(handicaps, dict):
        errors.append("challenge.handicaps must be an object")
    else:
        for stage, handicap in handicaps.items():
            if not str(stage).isdigit():
                errors.append(f"challenge.handicaps.{stage}: stage must be an integer string")
            if not isinstance(handicap, int) or handicap < 0:
                errors.append(f"challenge.handicaps.{stage}: handicap must be a non-negative integer")

    _validate_tuning(config, errors)
    return errors


def _apply_config(config: dict[str, Any], source_path: Path) -> None:
    global CARD_CONFIG_SOURCE_PATH, DEFAULT_ROGUE_META, DEFAULT_ULTIMATE_META

    cards = config["cards"]
    pools = config.get("pools", {})
    meta = config.get("meta", {})
    challenge = config.get("challenge", {})

    ROGUE_CARDS.clear()
    ROGUE_CARDS.update({card_id: _runtime_card(card) for card_id, card in cards["rogue"].items()})
    ULTIMATE_CARDS.clear()
    ULTIMATE_CARDS.update({card_id: _runtime_card(card) for card_id, card in cards["ultimate"].items()})

    ROGUE_FEATURED_CARDS.clear()
    ROGUE_FEATURED_CARDS.update(pools.get("rogue_featured", []))
    ULTIMATE_FEATURED_CARDS.clear()
    ULTIMATE_FEATURED_CARDS.update(pools.get("ultimate_featured", []))

    CHALLENGE_BETA_POOL.clear()
    CHALLENGE_BETA_POOL.extend(pools.get("challenge_beta", []))
    TWO_PLAYER_ROGUE_POOL.clear()
    TWO_PLAYER_ROGUE_POOL.extend(pools.get("two_player_rogue", []))
    AI_ROGUE_POOL.clear()
    AI_ROGUE_POOL.extend(pools.get("ai_rogue", []))
    AI_ULTIMATE_POOL.clear()
    AI_ULTIMATE_POOL.extend(pools.get("ai_ultimate", []))

    CHALLENGE_BETA_HANDICAPS.clear()
    CHALLENGE_BETA_HANDICAPS.update({int(stage): int(value) for stage, value in challenge.get("handicaps", {}).items()})
    CHALLENGE_CATEGORY_MAP.clear()
    CHALLENGE_CATEGORY_MAP.update(challenge.get("categories", {}))

    DEFAULT_ROGUE_META = copy.deepcopy(meta.get("rogue_defaults", DEFAULT_ROGUE_META))
    DEFAULT_ULTIMATE_META = copy.deepcopy(meta.get("ultimate_defaults", DEFAULT_ULTIMATE_META))
    ROGUE_CARD_META.clear()
    ROGUE_CARD_META.update(copy.deepcopy(meta.get("rogue", {})))
    ULTIMATE_CARD_META.clear()
    ULTIMATE_CARD_META.update(copy.deepcopy(meta.get("ultimate", {})))

    ACTIVE_CARD_CONFIG.clear()
    ACTIVE_CARD_CONFIG.update(copy.deepcopy(config))
    CARD_CONFIG_SOURCE_PATH = source_path


def reload_card_catalog() -> list[str]:
    path = _active_config_path()
    try:
        config = _load_json(path)
        errors = validate_card_config(config)
    except Exception as exc:
        errors = [f"{path}: {exc}"]
        CARD_CONFIG_ERRORS.clear()
        CARD_CONFIG_ERRORS.extend(errors)
        return errors
    if errors:
        CARD_CONFIG_ERRORS.clear()
        CARD_CONFIG_ERRORS.extend(errors)
        return errors
    _apply_config(config, path)
    CARD_CONFIG_ERRORS.clear()
    return []


def export_active_card_config() -> dict[str, Any]:
    return copy.deepcopy(ACTIVE_CARD_CONFIG)


def get_card_config_paths() -> dict[str, str]:
    return {
        "base": str(CARD_CONFIG_BASE_PATH),
        "user": str(CARD_CONFIG_USER_PATH),
        "active": str(CARD_CONFIG_SOURCE_PATH),
        "schema": str(CARD_CONFIG_SCHEMA_PATH),
    }


def get_card_config_editor_payload() -> dict[str, Any]:
    base_config: dict[str, Any] = {}
    schema: dict[str, Any] = {}
    try:
        base_config = _load_json(CARD_CONFIG_BASE_PATH)
    except Exception as exc:
        base_config = {"errors": [str(exc)]}
    try:
        schema = _load_json(CARD_CONFIG_SCHEMA_PATH)
    except Exception as exc:
        schema = {"errors": [str(exc)]}
    return {
        "ok": not CARD_CONFIG_ERRORS,
        "source": "user" if CARD_CONFIG_SOURCE_PATH == CARD_CONFIG_USER_PATH else "base",
        "paths": get_card_config_paths(),
        "errors": list(CARD_CONFIG_ERRORS),
        "config": export_active_card_config(),
        "base_config": base_config,
        "schema": schema,
    }


def _write_card_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup = path.with_suffix(f".{stamp}.bak.json")
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    payload = copy.deepcopy(config)
    payload.setdefault("$schema", "./cards.schema.json")
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_card_config(config: dict[str, Any]) -> dict[str, Any]:
    errors = validate_card_config(config)
    if errors:
        return {"ok": False, "errors": errors, "payload": get_card_config_editor_payload()}
    _write_card_config(CARD_CONFIG_USER_PATH, config)
    reload_errors = reload_card_catalog()
    return {
        "ok": not reload_errors,
        "errors": reload_errors,
        "payload": get_card_config_editor_payload(),
    }


def reset_card_config() -> dict[str, Any]:
    if CARD_CONFIG_USER_PATH.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup = CARD_CONFIG_USER_PATH.with_suffix(f".reset-{stamp}.bak.json")
        backup.write_text(CARD_CONFIG_USER_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        CARD_CONFIG_USER_PATH.unlink()
    reload_errors = reload_card_catalog()
    return {
        "ok": not reload_errors,
        "errors": reload_errors,
        "payload": get_card_config_editor_payload(),
    }


def get_gameplay_tuning_specs() -> dict[str, dict[str, Any]]:
    return copy.deepcopy(ACTIVE_CARD_CONFIG.get("tuning", {}))


def get_gameplay_tuning_values() -> dict[str, int | float]:
    values: dict[str, int | float] = {}
    for key, spec in ACTIVE_CARD_CONFIG.get("tuning", {}).items():
        value = spec.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values[key] = value
    return values


def _missing_pool_entries(pool_name: str, pool: Iterable[str], catalog: dict[str, dict[str, Any]]) -> list[str]:
    return [f"{pool_name}:{card_id}" for card_id in pool if card_id not in catalog]


def validate_card_catalog() -> list[str]:
    return validate_card_config(ACTIVE_CARD_CONFIG)


def assert_valid_card_catalog() -> None:
    errors = validate_card_catalog()
    if errors:
        raise ValueError("Invalid card catalog:\n" + "\n".join(errors))


def get_rogue_card(card_id: str) -> dict[str, Any]:
    return ROGUE_CARDS[card_id]


def get_ultimate_card(card_id: str) -> dict[str, Any]:
    return ULTIMATE_CARDS[card_id]


def rogue_card_meta(card_id: str) -> dict[str, str]:
    return {**DEFAULT_ROGUE_META, **ROGUE_CARD_META.get(card_id, {})}


def ultimate_card_meta(card_id: str) -> dict[str, str]:
    return {**DEFAULT_ULTIMATE_META, **ULTIMATE_CARD_META.get(card_id, {})}


def rogue_card_summary(card_id: str, locale: str = "zh-CN") -> dict[str, Any]:
    source = ACTIVE_CARD_CONFIG["cards"]["rogue"][card_id]
    card = get_rogue_card(card_id)
    return {
        "id": card_id,
        "name": _localized_value(source.get("name"), locale) or card["name"],
        "desc": _localized_value(source.get("desc"), locale) or card["desc"],
        "icon": card["icon"],
        "meta": rogue_card_meta(card_id),
        "i18n": _card_i18n(source),
    }


def ultimate_card_summary(card_id: str, locale: str = "zh-CN") -> dict[str, Any]:
    source = ACTIVE_CARD_CONFIG["cards"]["ultimate"][card_id]
    card = get_ultimate_card(card_id)
    return {
        "id": card_id,
        "name": _localized_value(source.get("name"), locale) or card["name"],
        "desc": _localized_value(source.get("desc"), locale) or card["desc"],
        "icon": card["icon"],
        "meta": ultimate_card_meta(card_id),
        "i18n": _card_i18n(source),
    }


def rogue_card_ids(pool: Iterable[str] | None = None, exclude: Iterable[str] | None = None) -> list[str]:
    excluded = set(exclude or [])
    source = list(pool) if pool is not None else list(ROGUE_CARDS.keys())
    return [card_id for card_id in source if card_id in ROGUE_CARDS and card_id not in excluded]


def ultimate_card_ids(exclude: Iterable[str] | None = None) -> list[str]:
    excluded = set(exclude or [])
    return [card_id for card_id in ULTIMATE_CARDS if card_id not in excluded]


def featured_rogue_cards(pool: Iterable[str] | None = None) -> list[str]:
    source = rogue_card_ids(pool)
    return [card_id for card_id in source if card_id in ROGUE_FEATURED_CARDS]


def featured_ultimate_cards(pool: Iterable[str] | None = None) -> list[str]:
    source = list(pool) if pool is not None else list(ULTIMATE_CARDS.keys())
    return [card_id for card_id in source if card_id in ULTIMATE_CARDS and card_id in ULTIMATE_FEATURED_CARDS]


def challenge_card_category(card_id: str) -> str | None:
    return CHALLENGE_CATEGORY_MAP.get(card_id)


def challenge_category_counts(cards: Iterable[str]) -> dict[str, int]:
    categories = ACTIVE_CARD_CONFIG.get("challenge", {}).get("allowed_categories", list(CHALLENGE_CATEGORIES))
    counts = {category: 0 for category in categories}
    for card_id in cards:
        category = challenge_card_category(card_id)
        if category:
            counts[category] = counts.get(category, 0) + 1
    return counts


def ai_rogue_cards(exclude: Iterable[str] | None = None) -> list[str]:
    return rogue_card_ids(AI_ROGUE_POOL, exclude=exclude)


def ai_ultimate_cards(exclude: Iterable[str] | None = None) -> list[str]:
    excluded = set(exclude or [])
    return [card_id for card_id in AI_ULTIMATE_POOL if card_id in ULTIMATE_CARDS and card_id not in excluded]


_startup_errors = reload_card_catalog()
if _startup_errors:
    raise ValueError("Invalid card config:\n" + "\n".join(_startup_errors))
