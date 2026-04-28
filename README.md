# GoAI Rogue Go Arena - WebView2 Desktop Edition

This branch is the Windows desktop edition of GoAI. It inherits the HTML
browser branch and adds a WebView2 shell around the same FastAPI backend,
WebSocket game runtime, and KataGo sidecar engine.

The HTML browser baseline lives on `codex/html-main`. Shared game, card, server,
and `static/index.html` changes should land there first, then this branch should
rebase or merge those updates.

## What This Version Is

GoAI is a local Go game powered by KataGo and a roguelike card layer. The
desktop edition keeps the web UI but launches it inside a native Windows
WebView2 window:

- `GoAI.exe` starts or reuses `GoAI_Server.exe`.
- `GoAI_Server.exe` serves `static/index.html` on `127.0.0.1:8000`.
- The desktop shell opens that URL with pywebview's Edge Chromium backend.
- KataGo remains an isolated sidecar under `katago/`.

This gives the app a desktop feel while keeping the HTML/WebSocket architecture
testable in a normal browser.

## Features

- WebView2 desktop shell by default.
- Edge app-window and system browser fallback.
- Classic AI games with KataGo.
- Rogue mode with 34 card effects.
- Ultimate mode with 25 high-impact cards.
- AI Rogue and local two-player Rogue variants.
- Local SGF export/import helpers.
- Chinese/English UI.
- GPU fallback order: CUDA, OpenCL, then CPU.
- Browser and runtime smoke tests remain valid.

## Branch Relationship

```text
codex/html-main
  original HTML browser edition
  owns shared HTML/server/card/game behavior

codex/webview2-desktop-migration
  inherits codex/html-main
  adds WebView2 launcher, packaging hooks, and desktop docs
```

When updating both editions, make common changes in `codex/html-main`, then
rebase this branch onto it:

```bash
git switch codex/webview2-desktop-migration
git rebase codex/html-main
```

## Requirements

- Windows 10 or 11 recommended.
- Python 3.11 or 3.12.
- Microsoft Edge WebView2 Runtime.
- Optional NVIDIA/OpenCL GPU for faster KataGo analysis.

Install Python dependencies:

```bash
pip install -r requirements.txt
```

`pywebview` is required for the default WebView2 shell:

```text
pywebview>=6.2,<7
```

Prepare or verify KataGo assets:

```bash
python setup.py
```

The installed app normally keeps large KataGo binaries and models in
`C:\Users\<you>\AppData\Local\GoAI\katago`. The repository only tracks config
files and placeholders, not the heavy model/runtime files.

## Run

Start the desktop app:

```bash
python launcher.py
```

The default shell is WebView2:

```bash
python launcher.py --shell webview
```

Fallback modes:

```bash
python launcher.py --shell edge
python launcher.py --shell browser
```

You can also set:

```powershell
$env:GOAI_DESKTOP_SHELL = "edge"
```

Run the backend directly for debugging:

```bash
python server.py --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

## Desktop Runtime Shape

```text
GoAI.exe
  starts/reuses GoAI_Server.exe
  opens WebView2 via pywebview
  falls back to Edge app-window or browser

GoAI_Server.exe
  serves HTML/assets
  owns WebSocket game state
  starts/stops KataGo

katago/*.exe
  isolated GTP engines
  can restart without taking down the desktop shell
```

See `docs/desktop-engine-migration.md` for the migration notes and smoke
checklist.

## Tests

Compile check:

```bash
python -m compileall launcher.py app server.py card_smoke_test.py runtime_smoke_test.py
```

Card and rules smoke test:

```bash
python card_smoke_test.py
```

Runtime smoke test against a running server:

```bash
python runtime_smoke_test.py --base-url http://127.0.0.1:8000
```

Desktop shell smoke:

```powershell
Start-Process .\GoAI.exe -ArgumentList "--shell", "webview"
```

Confirm that `msedgewebview2.exe` appears and `/status` reports
`static_ready: true`.

## Build

Build the WebView2 launcher:

```powershell
python -m PyInstaller --clean --noconfirm GoAI.spec
```

Build the server bundle:

```powershell
python -m PyInstaller --clean --noconfirm GoAI_Server.spec
```

Build the full installer:

```powershell
.\build_windows_release.ps1
```

The installer requires Inno Setup 6.

## Project Layout

```text
app/
  config/          Game and engine configuration
  data/            Rogue and Ultimate card catalogues
  domain/          Board state and coordinate logic
  runtime/         Engine startup, WebSocket actions, game store
static/
  index.html       Main HTML game client loaded by WebView2
  assets/          Board, stone, texture, toolbar, and card assets
docs/
  desktop-engine-migration.md
katago/
  config.cfg       KataGo GPU config
  config_cpu.cfg   KataGo CPU config
server.py          FastAPI backend
launcher.py        WebView2 desktop launcher
runtime_smoke_test.py
card_smoke_test.py
```

## License

MIT. See `LICENSE` and `THIRD_PARTY_NOTICES.md`.
