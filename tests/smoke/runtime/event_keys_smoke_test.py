"""Keyed server messages have a template in every locale pack and render cleanly.

Collects every ``event_text("<key>", zh, **params)`` call in the server code and
checks that:
- each key has a template in all seven locale packs (and no pack has orphans);
- templates only use placeholders the server actually sends;
- every template renders with the real client code (static/js/event_text.js)
  without leftover placeholders or text in the wrong script.
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
LOCALES = ["zh-CN", "zh-TW", "en-US", "ja-JP", "ko-KR", "fr-FR", "de-DE"]
PLACEHOLDER = re.compile(r"\{(\w+)(?:\|([^{}]+))?\}")
KNOWN_TYPES = {"card", "ucard", "color", "corner", "set", "rank", "list", "chain", "pl"}


def collect_calls() -> list[dict]:
    calls = []
    for path in [ROOT / "server.py", *sorted((ROOT / "app").rglob("*.py"))]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and ast.unparse(node.func).split(".")[-1] == "event_text"):
                continue
            if not node.args:
                continue
            key_node = node.args[0]
            names = {kw.arg for kw in node.keywords if kw.arg}
            dynamic_params = any(kw.arg is None for kw in node.keywords)
            constants = {
                kw.arg: kw.value.value
                for kw in node.keywords
                if kw.arg and isinstance(kw.value, ast.Constant)
            }
            where = f"{path.relative_to(ROOT).as_posix()}:{node.lineno}"
            if isinstance(key_node, ast.Constant):
                calls.append({"key": key_node.value, "pattern": None, "names": names,
                              "dynamic": dynamic_params, "constants": constants, "where": where})
            elif isinstance(key_node, ast.JoinedStr):
                regex = "".join(
                    re.escape(part.value) if isinstance(part, ast.Constant) else r"[a-z_]+"
                    for part in key_node.values
                )
                calls.append({"key": None, "pattern": re.compile(f"^{regex}$"), "names": names,
                              "dynamic": dynamic_params, "constants": constants, "where": where})
            else:
                raise AssertionError(f"{where}: event_text key must be a literal or f-string")
    return calls


def load_packs() -> dict[str, dict]:
    return {loc: json.loads((ROOT / "static" / "locales" / f"{loc}.json").read_text(encoding="utf-8")) for loc in LOCALES}


def sample_params(template_texts: list[str], constants: dict, key: str = "") -> list[dict]:
    """Two sample param sets per key (singular and plural numbers)."""
    if key.startswith("card.") and "card" not in constants:
        constants = {**constants, "card": key.split(".")[1]}
    by_name: dict[str, set[str]] = {}
    for text in template_texts:
        for name, spec in PLACEHOLDER.findall(text):
            by_name.setdefault(name, set()).add((spec or "").split(":")[0])
    samples = []
    for number in (1, 3):
        params = {}
        for name, types in by_name.items():
            if name in constants:
                params[name] = constants[name]
            elif "card" in types:
                params[name] = "sprout"
            elif "ucard" in types:
                params[name] = "meteor"
            elif "color" in types:
                params[name] = "B"
            elif "corner" in types:
                params[name] = "br"
            elif "set" in types:
                params[name] = ["trap", "zone"]
            elif "rank" in types:
                params[name] = "a3d"
            elif types & {"list", "chain"}:
                params[name] = ["D4", "K10", "Q16"]
            elif "pl" in types or name in {"count", "remaining", "streak", "shapes", "passes", "n"}:
                params[name] = number
            elif name in {"point", "from_point", "to_point", "target"}:
                params[name] = "D4"
            else:
                params[name] = number
        samples.append(params)
    return samples


HARNESS = r"""
const fs = require("fs"), vm = require("vm"), path = require("path");
const root = process.argv[1];
const read = rel => fs.readFileSync(path.join(root, rel), "utf8");
const sandbox = {
  console, URLSearchParams, Intl,
  window: { location: { search: "" } },
  navigator: { languages: ["zh-CN"], language: "zh-CN" },
  localStorage: { getItem: () => null, setItem() {} },
};
vm.createContext(sandbox);
for (const file of ["i18n.js", "card_catalog.js", "server_event_i18n.js", "event_text.js"]) {
  vm.runInContext(read(`static/js/${file}`), sandbox, { filename: file });
}
const langs = { "zh-CN": "zh", "zh-TW": "zht", "en-US": "en", "ja-JP": "ja", "ko-KR": "ko", "fr-FR": "fr", "de-DE": "de" };
for (const [file, lang] of Object.entries(langs)) {
  sandbox.__pack = JSON.parse(read(`static/locales/${file}.json`));
  vm.runInContext(`localeCache[${JSON.stringify(lang)}] = __pack;`, sandbox);
}
const jobs = JSON.parse(fs.readFileSync(0, "utf8"));
const out = [];
for (const job of jobs) {
  vm.runInContext(`currentLang = ${JSON.stringify(langs[job.locale])};`, sandbox);
  out.push(sandbox.localizeServerEvent("<legacy>", job.key, job.params));
}
process.stdout.write(JSON.stringify(out));
"""

CJK = re.compile(r"[㐀-鿿぀-ヿ가-힯]")
KANA = re.compile(r"[぀-ヿ]")
HANGUL = re.compile(r"[가-힯]")


def main() -> None:
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        raise RuntimeError("node is required for the event keys smoke test")
    calls = collect_calls()
    packs = load_packs()
    problems: list[str] = []

    pack_keys = {loc: set(pack.get("events", {})) for loc, pack in packs.items()}
    all_keys = set().union(*pack_keys.values())
    for loc, keys in pack_keys.items():
        for key in sorted(all_keys - keys):
            problems.append(f"{loc}: missing template for {key}")

    calls_by_key: dict[str, list[dict]] = {}
    for call in calls:
        if call["key"] is not None:
            calls_by_key.setdefault(call["key"], []).append(call)
            if call["key"] not in all_keys:
                problems.append(f"{call['where']}: no template for {call['key']}")
        else:
            matches = [key for key in all_keys if call["pattern"].match(key)]
            if not matches:
                problems.append(f"{call['where']}: no template matches {call['pattern'].pattern}")
            for key in matches:
                calls_by_key.setdefault(key, []).append(call)
    for key in sorted(all_keys - set(calls_by_key)):
        problems.append(f"orphan template {key} (no event_text call sends it)")

    jobs = []
    for key in sorted(calls_by_key):
        texts = [packs[loc]["events"][key] for loc in LOCALES if key in packs[loc].get("events", {})]
        for text in texts:
            for name, spec in PLACEHOLDER.findall(text):
                kind = (spec or "").split(":")[0]
                if kind and kind not in KNOWN_TYPES:
                    problems.append(f"{key}: unknown placeholder type {kind!r}")
                for call in calls_by_key[key]:
                    if not call["dynamic"] and name not in call["names"]:
                        problems.append(f"{call['where']}: {key} template uses {{{name}}} but the call does not send it")
        constants = {}
        for call in calls_by_key[key]:
            constants.update(call["constants"])
        if key.startswith("card.") and "card" in constants and constants["card"] != key.split(".")[1]:
            problems.append(f"{key}: card param {constants['card']!r} does not match the key")
        for params in sample_params(texts, constants, key):
            for loc in LOCALES:
                jobs.append({"key": key, "locale": loc, "params": params})

    result = subprocess.run([node, "-e", HARNESS, str(ROOT)], input=json.dumps(jobs),
                            capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(result.stderr)
    rendered = json.loads(result.stdout)
    for job, text in zip(jobs, rendered):
        where = f"{job['locale']} {job['key']}"
        if text == "<legacy>":
            problems.append(f"{where}: fell back to the legacy text")
        if "{" in text or "}" in text:
            problems.append(f"{where}: leftover placeholder in {text!r}")
        if job["locale"] in {"en-US", "fr-FR", "de-DE"} and CJK.search(text):
            problems.append(f"{where}: CJK text in {text!r}")
        if job["locale"] == "ja-JP" and HANGUL.search(text):
            problems.append(f"{where}: Hangul in Japanese {text!r}")
        if job["locale"] == "ko-KR" and KANA.search(text):
            problems.append(f"{where}: kana in Korean {text!r}")
    if problems:
        raise AssertionError(f"{len(problems)} event key problems:\n" + "\n".join(problems))
    print(f"event keys smoke test: OK ({len(calls_by_key)} keys x {len(LOCALES)} locales)")


if __name__ == "__main__":
    main()
