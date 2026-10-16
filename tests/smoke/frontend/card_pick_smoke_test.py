"""Card pick screen: every card has round art, Rogue cards have a summary and a type,
and nothing on the pick screen is truncated."""

from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOCALES = ["zh-CN", "zh-TW", "en-US", "ja-JP", "ko-KR", "fr-FR", "de-DE"]
SUMMARY_MAX_EN = 110


def main() -> None:
    config = json.loads((ROOT / "app" / "data" / "cards.json").read_text(encoding="utf-8"))
    packs = {loc: json.loads((ROOT / "static" / "locales" / f"{loc}.json").read_text(encoding="utf-8")) for loc in LOCALES}
    catalog = (ROOT / "static" / "js" / "card_catalog.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "legacy.css").read_text(encoding="utf-8")
    problems: list[str] = []

    art_dir = ROOT / "static" / "assets" / "icons" / "cards-medal"
    for mode in ("rogue", "ultimate"):
        for card_id in config["cards"][mode]:
            if not (art_dir / f"{card_id}.png").exists():
                problems.append(f"{mode}.{card_id}: no medallion art")
            if f'"{card_id}"' not in catalog.split("const CARD_ART_IDS", 1)[1].split("]);", 1)[0]:
                problems.append(f"{mode}.{card_id}: missing from CARD_ART_IDS")

    kinds_block = catalog.split("const ROGUE_CARD_KINDS", 1)[1].split("};", 1)[0]
    kinded = re.findall(r'"([a-z_]+)"', kinds_block)
    for card_id, card in config["cards"]["rogue"].items():
        if kinded.count(card_id) != 1:
            problems.append(f"rogue.{card_id}: needs exactly one type in ROGUE_CARD_KINDS")
        summary = card.get("summary", {})
        for loc in LOCALES:
            if not summary.get(loc, "").strip():
                problems.append(f"rogue.{card_id}: no {loc} summary in cards.json")
            if not packs[loc]["cards"]["rogue"][card_id].get("summary", "").strip():
                problems.append(f"rogue.{card_id}: no summary in the {loc} pack")
        if len(summary.get("en-US", "")) > SUMMARY_MAX_EN:
            problems.append(f"rogue.{card_id}: English summary longer than {SUMMARY_MAX_EN} characters")
        if summary.get("en-US") == card["desc"].get("en-US"):
            problems.append(f"rogue.{card_id}: summary just repeats the description")

    for selector in (".draft-card .rc-summary", ".draft-card .rc-rules"):
        block = css.split(selector + " {", 1)[1].split("}", 1)[0] if selector + " {" in css else ""
        if not block:
            problems.append(f"legacy.css: no rule for {selector}")
        elif "line-clamp" in block or "text-overflow" in block:
            problems.append(f"legacy.css: {selector} must not truncate")

    if problems:
        raise AssertionError(f"{len(problems)} card pick problems:\n" + "\n".join(problems))
    print(f"card pick smoke test: OK ({len(config['cards']['rogue'])} rogue cards)")


if __name__ == "__main__":
    main()
