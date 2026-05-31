# Smoke Tests

Smoke implementations are grouped by subsystem so the repository root stays
focused on product entry points and packaging files.

Current groups:

- `ai/`: AI move planning, AI turn flow, coach mode, and generated AI flows.
- `cards/`: card effects, rogue/challenge cards, turn modifiers, and balance scoring.
- `gameplay/`: board state, move history, ranks, and SGF helpers.
- `installers/`: installer and uninstaller contract checks.
- `runtime/`: HTTP routes, status payloads, engine gateway, static files, and startup compatibility.
- `websocket/`: WebSocket route, context, session, action, and endpoint smoke coverage.

Run a script directly:

```powershell
python tests/smoke/websocket/ws_play_actions_smoke_test.py
```

Or use the smoke runner by filename:

```powershell
python -m tests.smoke.run ws_play_actions_smoke_test.py
python -m tests.smoke.run --list
```
