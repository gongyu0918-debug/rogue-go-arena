# -*- coding: utf-8 -*-
"""Smoke test for legacy server-event message translations."""

from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "static" / "js" / "server_event_i18n.js"


def main() -> None:
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        raise RuntimeError("node is required for legacy event i18n smoke test")

    harness = f"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync({json.dumps(str(SCRIPT_PATH))}, "utf8");
const sandbox = {{ currentLang: "zh", console }};
vm.createContext(sandbox);
vm.runInContext(source, sandbox, {{ filename: "server_event_i18n.js" }});

function expect(lang, input, expected) {{
  sandbox.currentLang = lang;
  const actual = sandbox.translateServerEventMessage(input);
  if (actual !== expected) {{
    throw new Error(`${{lang}} translation mismatch for ${{JSON.stringify(input)}}\\nexpected: ${{JSON.stringify(expected)}}\\nactual:   ${{JSON.stringify(actual)}}`);
  }}
}}

function expectNoCjk(lang, input) {{
  sandbox.currentLang = lang;
  const actual = sandbox.translateServerEventMessage(input);
  if (/[\\u3040-\\u30ff\\u3400-\\u9fff\\uac00-\\ud7af]/.test(actual)) {{
    throw new Error(`${{lang}} translation still contains CJK for ${{JSON.stringify(input)}}: ${{JSON.stringify(actual)}}`);
  }}
}}

expect("zh", "打劫禁着：不能立即提回", "打劫禁着：不能立即提回");
expect("en", "打劫禁着：不能立即提回", "Ko rule: you cannot immediately recapture.");
expect("ja", "打劫禁着：不能立即提回", "コウの禁着：すぐに取り返せません");
expect("ko", "打劫禁着：不能立即提回", "패 금지: 즉시 되따낼 수 없습니다");
expect("fr", "打劫禁着：不能立即提回", "Regle du ko : reprise immediate interdite.");
expect("de", "打劫禁着：不能立即提回", "Ko-Regel: Sofortiges Zurueckschlagen ist verboten.");
expect("en", "黄金角已封锁 左上角 的 4x4 区域", "Golden Corner sealed the 4x4 area in the top-left corner.");
expect("ja", "黄金角已封锁 左上角 的 4x4 区域", "黄金角が左上隅の4x4領域を封鎖しました");
expect("ko", "黄金角已封锁 左上角 的 4x4 区域", "황금귀가 좌상귀의 4x4 구역을 봉쇄했습니다");
expect("fr", "黄金角已封锁 左上角 的 4x4 区域", "Le Coin d'or a verrouille la zone 4x4 du coin supérieur gauche.");
expect("de", "黄金角已封锁 左上角 的 4x4 区域", "Goldenes Eck hat das 4x4-Gebiet im oberen linken Eck gesperrt.");
expect("zht", "黄金角已封锁 左上角 的 4x4 区域", "黃金角已封鎖 左上角 的 4x4 區域");
expect("ja", "你可以继续落子", "続けて着手できます");
expect("ko", "你可以继续落子", "계속 착수할 수 있습니다");
expect("fr", "🧺 提子犯规触发！黑棋 提子达到 4 颗，在我方推荐点 D4 赠送 1 颗己棋", "🧺 Faute de capture declenchee : Noir atteint 4 captures ; 1 pierre alliee offerte au point recommande D4.");
expect("de", "🧺 提子犯规触发！白棋 提子达到 4 颗，在我方推荐点 Q16 赠送 1 颗己棋", "🧺 Schlag-Foul ausgelost: Weiss erreicht 4 geschlagene Steine; 1 verbuendeter Stein auf Empfehlungspunkt Q16 gesetzt.");
expect("fr", "△ 三三陷阱发动，在 D4 相邻点反打 2 子", "△ Piege 3-3 declenche : 2 contre-pierres posees pres de D4.");
expect("de", "🚫 永不悔棋发动，AI 落子后在 Q16 赠送一子", "🚫 Keine Reue nach dem KI-Zug ausgelost: 1 verbuendeter Stein auf Q16 gesetzt.");
expect("fr", "🔄 乾坤挪移：已将对方 D4 的棋子摆动到 E5", "🔄 Echange cosmique : la pierre adverse en D4 est deplacee vers E5.");
expect("de", "🎓 代练上号：强化 AI 接管了一手，剩余 2 手", "🎓 KI-Coach: Die verstaerkte KI hat einen Zug gespielt. 2 Zug/Zuege uebrig.");
expect("fr", "🧺 提子犯规触发！黑棋 提子达到 4 颗，但当前没有可用推荐点", "🧺 Faute de capture declenchee : Noir atteint 4 captures, mais aucun point recommande n'est disponible.");
expect("de", "🧺 提子犯规触发！白棋 被罚 5 目", "🧺 Schlag-Foul ausgelost: Weiss erhaelt 5 Punkte Strafe.");
expect("fr", "让子任务奖励触发：每满 10 手获得一次奖励，当前进度 1/2，AI 将虚手一次", "Bonus de mission handicap : recompense tous les 10 coups. Progression 1/2, l'IA passera une fois.");
expect("fr", "🏋️ 让子棋任务完成！", "🏋️ Mission handicap terminee.");
expect("de", "🏋️ 让子棋任务完成！", "🏋️ Handicap-Mission abgeschlossen.");
expect("fr", "请选择对方棋子和目标空点", "Selectionnez une pierre adverse et un point vide cible.");
expect("de", "乾坤挪移只能移动对方棋子", "Kosmische Rochade kann nur gegnerische Steine bewegen.");
expect("fr", "目标位置必须是空点", "Le point cible doit etre vide.");
expect("zht", "暫无进行中的对局", "暫無進行中的對局");
expect("zht", "黑洞已锁定中央区域，整局都会限制 AI 进入", "黑洞已鎖定中央區域，整局都會限制 AI 進入");
for (const sample of [
  "暂无进行中的对局",
  "黄金角已封锁 左上角 的 4x4 区域",
  "🛡 防御至上触发：在 D4 赠送 1 颗己棋，本局剩余 1 次",
  "⚔ 进攻至上触发：在 Q16 赠送 1 颗己棋，本局剩余 0 次",
  "🌫 战争迷雾残留：本回合随机封锁 1 个 AI 禁着点",
  "🧺 提子犯规触发！黑棋 提子达到 4 颗，在我方推荐点 D4 赠送 1 颗己棋",
  "△ 三三陷阱发动，在 D4 相邻点反打 2 子",
  "🚫 永不悔棋发动，AI 落子后在 Q16 赠送一子",
  "🔄 乾坤挪移：已将对方 D4 的棋子摆动到 E5",
  "🎓 代练上号：强化 AI 接管了一手，剩余 2 手",
  "🧺 提子犯规触发！黑棋 提子达到 4 颗，但当前没有可用推荐点",
  "🧺 提子犯规触发！白棋 被罚 5 目",
  "让子任务奖励触发：每满 10 手获得一次奖励，当前进度 1/2，AI 将虚手一次",
  "🏋️ 让子棋任务完成！",
  "请选择对方棋子和目标空点",
  "乾坤挪移只能移动对方棋子",
  "目标位置必须是空点",
]) {{
  expectNoCjk("fr", sample);
  expectNoCjk("de", sample);
}}
expect("en", "unmatched server event", "unmatched server event");

console.log("legacy event i18n smoke test: OK");
"""
    result = subprocess.run([node, "-e", harness], capture_output=True, text=True, check=False)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    result.check_returncode()


if __name__ == "__main__":
    main()
