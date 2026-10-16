"""Every player-visible server message is translated in every UI language.

Server messages are Chinese source strings that the legacy UI translates on the
client (static/js/server_event_i18n.js plus exact phrases in the locale packs).
This test extracts the message templates from the gameplay and websocket code,
fills their placeholders with sample values, and fails if en/fr/de still show
CJK text or ja/ko return the Chinese source unchanged. It keeps translations
from silently drifting when server wording changes.
"""

from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import ast
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CJK = re.compile(r"[㐀-鿿]")
SCOPE = [
    ROOT / "server.py",
    *sorted((ROOT / "app" / "gameplay").rglob("*.py")),
    *sorted((ROOT / "app" / "runtime").glob("ws_*.py")),
]
SKIP_CALLS = {"log", "log_fn", "print", "engine_log", "_log", "warning", "info", "debug", "ValueError", "RuntimeError"}

# Pieces the server stitches into longer messages (or passes as values); the
# assembled results are covered by ASSEMBLED below.
FRAGMENTS = {
    "三三陷阱", "神之一手", "黑棋", "白棋", "左上角", "右上角", "左下角", "右下角",
    "衍生", "陷阱", "限位", "限制", "主动", "🛡 防御至上", "⚔ 进攻至上", "💥 排异反应！",
    "{}触发：在 {} 赠送 1 颗己棋，本局剩余 {} 次", "挤走 {} 子", "{}摧毁 {} 子",
    "🧲 磁力吸附！{} 子飞奔", "，碾碎 {} 颗敌子", "{}，在我方推荐点 {} 赠送 1 颗己棋",
    "{}，但当前没有可用推荐点", "🧺 提子犯规触发！{} 提子达到 {} 颗", "? AI 返回已占用点 {}，已停止落子",
}
ASSEMBLED = [
    "🛡 防御至上触发：在 D4 赠送 1 颗己棋，本局剩余 1 次",
    "⚔ 进攻至上触发：在 Q16 赠送 1 颗己棋，本局剩余 0 次",
    "💥 排异反应！挤走 2 子，摧毁 1 子",
    "💥 排异反应！挤走 2 子",
    "💥 排异反应！摧毁 1 子",
    "🧲 磁力吸附！3 子飞奔",
    "🧲 磁力吸附！3 子飞奔，碾碎 2 颗敌子",
    "🧺 提子犯规触发！白棋 提子达到 4 颗，在我方推荐点 D4 赠送 1 颗己棋",
    "🧺 提子犯规触发！黑棋 提子达到 4 颗，但当前没有可用推荐点",
    "AI 引擎落子失败：? AI 返回已占用点 D4，已停止落子",
    "陷阱套装触发：三三陷阱 额外夺得一次落子权",
    "陷阱套装触发：神之一手 额外夺得一次落子权",
    "限制套装触发：AI 临时下调至 业余3段",
    "限制套装触发：AI 临时下调至 职业二段",
    "限制套装触发：AI 临时下调至 5级",
    "闯关套装已激活：陷阱 / 限位",
    "黄金角已封锁 右下角 的 4x4 区域，整局都会限制 AI 进入",
]


def sample_for(expr: str) -> str:
    e = expr.lower()
    if "coord_to_gtp" in e or e in ("gtp", "from_gtp", "to_gtp", "point_label", "mirror_gtp", "where"):
        return "D4"
    if "gameplay_config." in e or e.startswith(("rogue_", "ultimate_")):
        return "3"
    if "cols[" in e:
        return "K"
    if "color" in e:
        return "黑棋"
    if any(k in e for k in ("count", "span", "size", "remaining", "hits", "total", "len(", "stage", "turns", "left",
                            "captured", "penalty", "threshold", "required", "interval", "passes", "progress",
                            "stones", "cleared", "changed", "placed", "generated", "shapes", "wave", "streak",
                            "uses", "bonus", "extra", "radius", "moved", "crushed", "pushed", "destroyed")):
        return "3"
    if "corner" in e:
        return "左上角"
    if "komi" in e:
        return "6.5"
    if any(k in e for k in ("names", "pts", "stars")):
        return "D4, Q16"
    if any(k in e for k in ("gtp", "coord", "point", "target")):
        return "D4"
    if any(k in e for k in ("exc", "err", "reason", "resp", "detail", "action")):
        return "boom"
    return "3"


def literal_cjk(node) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return bool(CJK.search(node.value))
    if isinstance(node, ast.JoinedStr):
        return any(isinstance(p, ast.Constant) and CJK.search(str(p.value)) for p in node.values)
    if isinstance(node, ast.BinOp):
        return literal_cjk(node.left) or literal_cjk(node.right)
    return False


def render(node, placeholder=None):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = []
        for part in node.values:
            if isinstance(part, ast.Constant):
                out.append(str(part.value))
            elif isinstance(part, ast.FormattedValue):
                out.append(placeholder if placeholder is not None else sample_for(ast.unparse(part.value)))
        return "".join(out)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = render(node.left, placeholder), render(node.right, placeholder)
        if left is not None and right is not None:
            return left + right
    return None


class Collector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[ast.AST] = []
        self.found: dict[str, str] = {}

    def generic_visit(self, node):
        self.stack.append(node)
        super().generic_visit(node)
        self.stack.pop()

    def _consider(self, node, where: str) -> None:
        if not literal_cjk(node):
            return
        for anc in self.stack:
            if isinstance(anc, ast.Call) and ast.unparse(anc.func).split(".")[-1] in SKIP_CALLS:
                return
        parent = self.stack[-1] if self.stack else None
        if isinstance(parent, ast.Expr):
            return
        if isinstance(parent, ast.Dict) and node in parent.keys:
            return
        if render(node, "{}") in FRAGMENTS:
            return
        text = render(node)
        if text:
            self.found.setdefault(text, where)

    def visit_JoinedStr(self, node):
        self._consider(node, f"{self.path}:{node.lineno}")

    def visit_Constant(self, node):
        self._consider(node, f"{self.path}:{node.lineno}")

    def visit_BinOp(self, node):
        if literal_cjk(node) and render(node) is not None:
            self._consider(node, f"{self.path}:{node.lineno}")
            return
        self.generic_visit(node)


def collect_messages() -> dict[str, str]:
    collector = Collector()
    for path in SCOPE:
        collector.path = path.relative_to(ROOT).as_posix()
        collector.visit(ast.parse(path.read_text(encoding="utf-8")))
    messages = dict(collector.found)
    for text in ASSEMBLED:
        messages.setdefault(text, "assembled sample")
    return messages


HARNESS = r"""
const fs = require("fs"), vm = require("vm"), path = require("path");
const root = process.argv[1];
const read = rel => fs.readFileSync(path.join(root, rel), "utf8");
const sandbox = {
  console, URLSearchParams,
  window: { location: { search: "" } },
  navigator: { languages: ["zh-CN"], language: "zh-CN" },
  localStorage: { getItem: () => null, setItem() {} },
};
vm.createContext(sandbox);
vm.runInContext(read("static/js/i18n.js"), sandbox, { filename: "i18n.js" });
vm.runInContext(read("static/js/card_catalog.js"), sandbox, { filename: "card_catalog.js" });
vm.runInContext(read("static/js/server_event_i18n.js"), sandbox, { filename: "server_event_i18n.js" });
const packs = { zh: "zh-CN", zht: "zh-TW", en: "en-US", ja: "ja-JP", ko: "ko-KR", fr: "fr-FR", de: "de-DE" };
for (const [lang, file] of Object.entries(packs)) {
  sandbox.__pack = JSON.parse(read(`static/locales/${file}.json`));
  vm.runInContext(`localeCache[${JSON.stringify(lang)}] = __pack;`, sandbox);
}
const messages = JSON.parse(fs.readFileSync(0, "utf8"));
const out = {};
for (const text of messages) {
  out[text] = {};
  for (const lang of ["en", "fr", "de", "ja", "ko"]) {
    vm.runInContext(`currentLang = ${JSON.stringify(lang)};`, sandbox);
    out[text][lang] = sandbox.translateServerEventMessage(text);
  }
}
process.stdout.write(JSON.stringify(out));
"""

HAN_KANA_HANGUL = re.compile(r"[぀-ヿ㐀-鿿가-힯]")
KANA = re.compile(r"[぀-ヿ]")
HANGUL = re.compile(r"[가-힯]")


def main() -> None:
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        raise RuntimeError("node is required for the server event coverage smoke test")
    messages = collect_messages()
    assert len(messages) > 100, f"suspiciously few messages extracted: {len(messages)}"
    result = subprocess.run(
        [node, "-e", HARNESS, str(ROOT)],
        input=json.dumps(list(messages)), capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    translated = json.loads(result.stdout)
    problems = []
    for text, where in messages.items():
        t = translated[text]
        bad = [lang for lang in ("en", "fr", "de") if HAN_KANA_HANGUL.search(t[lang])]
        bad += [lang for lang in ("ja", "ko") if t[lang] == text]
        if KANA.search(t["ko"]) or HANGUL.search(t["ja"]):
            bad.append("ja/ko mixed")
        if bad:
            problems.append(f"{where}: [{', '.join(bad)}] {text}")
    if problems:
        raise AssertionError(f"{len(problems)} untranslated server messages:\n" + "\n".join(problems))
    print(f"server event coverage smoke test: OK ({len(messages)} messages x 5 languages)")


if __name__ == "__main__":
    main()
