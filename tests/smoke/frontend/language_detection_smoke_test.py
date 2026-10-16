"""The UI uses the player's system language when we ship it, else English."""

from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
I18N = ROOT / "static" / "js" / "i18n.js"
EDITOR = ROOT / "static" / "card_editor.html"

CASES = [
    # (url ?lang, stored choice, navigator.languages, navigator.language, expected)
    (None, None, ["es-ES", "en-US"], "es-ES", "en"),
    (None, None, ["es-ES", "ja-JP"], "es-ES", "ja"),
    (None, None, ["it-IT"], "it-IT", "en"),
    (None, None, [], "", "en"),
    (None, None, ["zh-CN"], "zh-CN", "zh"),
    (None, None, ["zh-SG"], "zh-SG", "zh"),
    (None, None, ["zh"], "zh", "zh"),
    (None, None, ["zh-HK"], "zh-HK", "zht"),
    (None, None, ["zh-Hant-TW"], "zh-Hant-TW", "zht"),
    (None, None, ["ko_KR"], "ko_KR", "ko"),
    (None, None, ["pt-BR", "fr-CA"], "pt-BR", "fr"),
    (None, "de", ["ja-JP"], "ja-JP", "de"),
    ("ko", "de", ["ja-JP"], "ja-JP", "ko"),
    ("xx", None, ["pt-PT"], "pt-PT", "en"),
]


def main() -> None:
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        raise RuntimeError("node is required for the language detection smoke test")
    html = EDITOR.read_text(encoding="utf-8")
    editor_fns = re.search(r"(    // Same rules as the game.*?\n    function detectLang\(candidates\) \{.*?\n    \})", html, re.S)
    assert editor_fns, "card editor language detection not found"

    harness = f"""
const fs = require("fs");
const vm = require("vm");
const i18n = fs.readFileSync({json.dumps(str(I18N))}, "utf8");
const editorFns = {json.dumps(editor_fns.group(1))};
const cases = {json.dumps(CASES)};
for (const [urlLang, stored, languages, language, expected] of cases) {{
  const sandbox = {{
    console,
    URLSearchParams,
    window: {{ location: {{ search: urlLang ? `?lang=${{urlLang}}` : "" }} }},
    navigator: {{ languages, language }},
    localStorage: {{ getItem: key => (key === "rogue_go_arena_lang" ? stored : null) }},
  }};
  vm.createContext(sandbox);
  vm.runInContext(i18n + "\\n;globalThis.__lang = currentLang;", sandbox);
  if (sandbox.__lang !== expected) {{
    throw new Error(`game: ${{JSON.stringify([urlLang, stored, languages, language])}} -> ${{sandbox.__lang}}, expected ${{expected}}`);
  }}
  const editor = {{}};
  vm.createContext(editor);
  vm.runInContext(editorFns + "\\n;globalThis.__lang = detectLang([" +
    JSON.stringify(stored) + ", ...(" + JSON.stringify(languages) + "), " + JSON.stringify(language) + "]);", editor);
  const editorExpected = urlLang ? null : expected;
  if (editorExpected && editor.__lang !== editorExpected) {{
    throw new Error(`editor: ${{JSON.stringify([stored, languages, language])}} -> ${{editor.__lang}}, expected ${{editorExpected}}`);
  }}
}}
// A localStorage that throws (private mode, blocked site data) must not break detection.
const broken = {{
  console, URLSearchParams,
  window: {{ location: {{ search: "" }} }},
  navigator: {{ languages: ["ja-JP"], language: "ja-JP" }},
  localStorage: {{ getItem() {{ throw new Error("blocked"); }} }},
}};
vm.createContext(broken);
vm.runInContext(i18n + "\\n;globalThis.__lang = currentLang;", broken);
if (broken.__lang !== "ja") throw new Error("blocked storage broke detection: " + broken.__lang);
console.log("language detection smoke test: OK");
"""
    result = subprocess.run([node, "-e", harness], capture_output=True, text=True, encoding="utf-8")
    print(result.stdout, end="")
    if result.returncode:
        print(result.stderr)
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
