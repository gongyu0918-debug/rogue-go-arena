# rogue-go-arena Agent Handoff

## Workspace

- Primary workspace: `F:\Workspaces\rogue go project\rogue-go-arena`
- Historical/source mirror: `F:\Workspaces\Playground\projects\apps\rogue-goai`
- Main branch is the local development line. React architecture work should happen on `refactor/react-card-architecture` until parity smoke is strong enough to merge.
- Do not push, publish, rebuild the installer, or overwrite `F:\rogue-go-arena` unless explicitly asked.

## Current Architecture Direction

- Keep the existing classic frontend as the stable production root while React is built in parallel.
- React/Vite/TypeScript lives under `frontend/` and builds to `static/react/`.
- `/react-preview` serves the React build. `/` and `/card-editor` remain legacy/stable until feature parity is verified.
- Runtime browser compatibility must include Edge/WebView2 109 as the practical old-PC floor. Vite targets `chrome109` and `edge109`.
- Use React for typed UI/state boundaries and Canvas for board rendering. Avoid large game engines.
- Community Go/SGF packages are spike/test-oracle candidates, not automatic replacements for stable custom code.
- Python backend remains authoritative for Go rules, Rogue/Ultimate effects, AI move orchestration, and scoring.

## Verification Baseline

- Before commit: `git diff --check`
- Frontend: `npm run typecheck --prefix frontend`, `npm run build --prefix frontend`
- React preview browser smoke: start `server.py --no-katago --port 8876`, then `npm run smoke:react-preview --prefix frontend -- --url=http://127.0.0.1:8876/react-preview`
- Python syntax: prefer AST parse smoke when Windows pycache permissions block `compileall`
- Card rules: `python tests/smoke/cards/card_smoke_test.py`
- Card editor/effects: `python tests/smoke/cards/card_editor_effect_smoke.py`
- Runtime/AI/WebSocket changes: real KataGo `python tests/smoke/runtime/runtime_smoke_test.py --base-url http://127.0.0.1:<port>`

## Release Guardrails

- Release script must build the React frontend before PyInstaller/Inno.
- Installer smoke must validate installed `/status`, root, `/react-preview`, `/legacy` once added, and `/card-editor`.
- Keep old-machine fallback practical: WebView2, Edge app-window, and browser fallback should still open the app.
