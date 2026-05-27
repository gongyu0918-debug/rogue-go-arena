from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "rogue-go-arena_Setup.iss"
LANGUAGES = ("chinesesimplified", "english", "japanese", "korean")


def read_script() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def section(script: str, name: str) -> str:
    match = re.search(rf"^\[{re.escape(name)}\]\s*$", script, re.MULTILINE)
    if not match:
        return ""
    next_match = re.search(r"^\[[^\]]+\]\s*$", script[match.end():], re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(script)
    return script[match.end():end]


def custom_message_keys(custom_messages: str) -> dict[str, set[str]]:
    keys: dict[str, set[str]] = {language: set() for language in LANGUAGES}
    for line in custom_messages.splitlines():
        line = line.strip()
        if not line or line.startswith(";") or "." not in line or "=" not in line:
            continue
        prefix, rest = line.split(".", 1)
        key, _value = rest.split("=", 1)
        if prefix in keys:
            keys[prefix].add(key)
    return keys


def main() -> int:
    script = read_script()
    languages = section(script, "Languages")
    custom_messages = section(script, "CustomMessages")
    icons = section(script, "Icons")
    uninstall_delete = section(script, "UninstallDelete")
    code = section(script, "Code")

    missing = []
    for language in LANGUAGES:
        if f'Name: "{language}"' not in languages:
            missing.append(f"missing [Languages] entry for {language}")

    keys = custom_message_keys(custom_messages)
    all_keys = set().union(*keys.values())
    for language in LANGUAGES:
        for key in sorted(all_keys):
            if key not in keys[language]:
                missing.append(f"missing {language}.{key} custom message")

    required_fragments = {
        "start menu uninstall shortcut": "{cm:UninstallProgram,{#MyAppName}}",
        "uninstall temp cleanup": r'Name: "{app}\katago\is-*.tmp"',
        "uninstall local-data prompt": "RemoveUserDataPrompt",
        "uninstall hook": "function InitializeUninstall()",
        "uninstall defaults to keeping user data": "MB_YESNO or MB_DEFBUTTON2",
        "uninstall generated log cleanup": r"DelTree(ExpandConstant('{app}\gtp_logs'), True, True, True)",
        "uninstall output cleanup": r"DelTree(ExpandConstant('{app}\output'), True, True, True)",
        "uninstall downloaded model cleanup": r"DeleteFile(ExpandConstant('{app}\katago\model.bin.gz'))",
        "uninstall local data path": r"ExpandConstant('{localappdata}\rogue-go-arena')",
        "uninstall local data cleanup": "DelTree(UserDataDir, True, True, True)",
    }
    search_scopes = {
        "start menu uninstall shortcut": icons,
        "uninstall temp cleanup": uninstall_delete,
        "uninstall local-data prompt": custom_messages + code,
        "uninstall hook": code,
        "uninstall defaults to keeping user data": code,
        "uninstall generated log cleanup": code,
        "uninstall output cleanup": code,
        "uninstall downloaded model cleanup": code,
        "uninstall local data path": code,
        "uninstall local data cleanup": code,
    }
    for label, fragment in required_fragments.items():
        if fragment not in search_scopes[label]:
            missing.append(f"missing {label}")

    guarded_cleanup = re.search(
        r"if\s*\(CurUninstallStep\s*=\s*usPostUninstall\)\s*and\s*"
        r"RemoveUserDataOnUninstall\s*then\s*begin(?P<body>.*?)end;",
        code,
        re.IGNORECASE | re.DOTALL,
    )
    if not guarded_cleanup:
        missing.append("missing guarded uninstall cleanup block")
    else:
        guarded_body = guarded_cleanup.group("body")
        for fragment in (
            r"DelTree(ExpandConstant('{app}\gtp_logs'), True, True, True)",
            r"DelTree(ExpandConstant('{app}\output'), True, True, True)",
            r"DeleteFile(ExpandConstant('{app}\katago\kata_log.txt'))",
            r"DeleteFile(ExpandConstant('{app}\katago\model.bin.gz'))",
            "DelTree(UserDataDir, True, True, True)",
        ):
            if fragment not in guarded_body:
                missing.append(f"unguarded or missing cleanup: {fragment}")

    forbidden_unguarded_deletes = (
        r"{app}\gtp_logs",
        r"{app}\output",
        r"{app}\katago\kata_log.txt",
        r"{app}\katago\model.bin.gz",
        r"{localappdata}\rogue-go-arena",
    )
    for fragment in forbidden_unguarded_deletes:
        if fragment in uninstall_delete:
            missing.append(f"user-data delete must be opt-in, not [UninstallDelete]: {fragment}")

    if missing:
        for item in missing:
            print(f"installer smoke test: {item}")
        return 1

    print("installer smoke test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
