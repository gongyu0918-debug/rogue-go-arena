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

expect("zh", "打劫禁着：不能立即提回", "打劫禁着：不能立即提回");
expect("en", "打劫禁着：不能立即提回", "Ko rule: you cannot immediately recapture.");
expect("ja", "打劫禁着：不能立即提回", "コウの禁着：すぐに取り返せません");
expect("ko", "打劫禁着：不能立即提回", "패 금지: 즉시 되따낼 수 없습니다");
expect("en", "黄金角已封锁 左上角 的 4x4 区域", "Golden Corner sealed the 4x4 area in the top-left corner.");
expect("ja", "黄金角已封锁 左上角 的 4x4 区域", "黄金角が左上隅の4x4領域を封鎖しました");
expect("ko", "黄金角已封锁 左上角 的 4x4 区域", "황금귀가 좌상귀의 4x4 구역을 봉쇄했습니다");
expect("fr", "黄金角已封锁 左上角 的 4x4 区域", "황금귀가 좌상귀의 4x4 구역을 봉쇄했습니다");
expect("ja", "你可以继续落子", "続けて着手できます");
expect("ko", "你可以继续落子", "계속 착수할 수 있습니다");
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
