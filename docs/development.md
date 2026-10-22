# Development notes

Everything here is for people working on the code. Players only need the
[README](../README.md).

## Run from source

You need Windows 10 or 11, Python 3.11, and the Microsoft Edge WebView2
Runtime. A GPU is optional.

```bash
pip install -r requirements.txt
python setup.py        # downloads the OpenCL and CPU KataGo engines and a model
python launcher.py     # starts the server and opens the game window
```

Pick the window type yourself if you need to:

```bash
python launcher.py --shell webview   # WebView2 window (default)
python launcher.py --shell edge      # Edge app window
python launcher.py --shell browser   # your default browser
```

Run only the server, for debugging in a normal browser:

```bash
python server.py --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000`. The card editor is at
`http://127.0.0.1:8000/card-editor` (players reach it from Settings).

The server and the card editor write to `%LOCALAPPDATA%\rogue-go-arena`. An
editor-saved `cards.json` there overrides `app/data/cards.json`, so point
`LOCALAPPDATA` at a scratch folder when you test.

## How the desktop app fits together

```text
rogue-go-arena.exe           launcher
  starts or reuses rogue-go-arena-server.exe
  opens a WebView2 window (falls back to an Edge app window, then the browser)

rogue-go-arena-server.exe    FastAPI + WebSocket server
  serves static/index.html and its assets
  owns the game state
  starts and stops KataGo on demand

katago/*.exe                 KataGo GTP engines
  picked in the order CUDA -> OpenCL -> CPU
  CUDA only when the optional CUDA upgrade (katago_cuda.exe plus its DLLs)
  is present and the NVIDIA driver is new enough
```

## Project layout

```text
app/
  config/          game and engine settings (tunable values live here)
  data/            card data (cards.json and its schema)
  domain/          board state and coordinates
  gameplay/        card effects, difficulty, run curve, AI move logic
  runtime/         WebSocket actions, engine startup, status
static/
  index.html       the game UI loaded by the window
  js/, locales/    UI scripts and the seven language packs
  assets/          board, stones, card art, icons
docs/              notes like this one; docs/assets holds README images
katago/            KataGo engines, configs and models (see katago/README.md)
tools/             developer tools, not shipped in the installer
tests/smoke/       smoke tests, grouped by subsystem
server.py          FastAPI backend
launcher.py        desktop launcher
```

Cards: the full plain-text config is [app/data/cards.json](../app/data/cards.json),
checked by [app/data/cards.schema.json](../app/data/cards.schema.json). The game
reloads it at the start of every game.

KataGo files: engines, models and runtime DLLs are not committed. `setup.py`
or a release package provides them. See [katago/README.md](../katago/README.md).

## Tests

The smoke tests are plain scripts, no pytest needed:

```bash
python tests/smoke/cards/card_smoke_test.py
python -m tests.smoke.run card_smoke_test.py      # run one by file name
```

A few need extra setup: the card-editor and WebView checks need Playwright or
pywebview, `ko_engine_smoke_test.py` needs `--katago-dir katago --backend opencl`,
and `runtime_smoke_test.py` needs `--base-url http://127.0.0.1:8000`
(`source_runtime_smoke_test.py` starts its own server and runs it for you).

## Balance tools

- `tools/card_balance_eval.py`: measures one card at a time in self-play.
- `tools/run_curve_eval.py`: plays whole runs or Quick Games against the
  standard AI. `--player-level` gives your side a weaker engine, `--set KEY=VALUE`
  overrides a tuning value, `--quick-card CARD` plays Rogue-mode games
  (`--quick-card none` without a card, as a baseline).
- `tools/card_art/`: regenerates the round card art (see [tools/README.md](../tools/README.md)).

Results and the reasoning behind the current numbers:
[balance update 0.1.42](balance-update-20261016.md),
[run curve calibration](run-curve-calibration-20261013.md),
[card values](card-values-20261013.md).

## Building the installer

You need PyInstaller (the script finds a Python that has it, or pass
`-PythonExe`), Node.js and npm, Inno Setup 6, and the KataGo files in
`katago/`, including the CPU fallback `katago_cpu.exe` (run `python setup.py`).

```powershell
.\build_windows_release.ps1 -Version 0.1.42
```

The installer lands in `release/`. To build the parts by hand:

```powershell
python -m PyInstaller --clean --noconfirm rogue-go-arena.spec
python -m PyInstaller --clean --noconfirm rogue-go-arena-server.spec
```

## Branches

- `webview`: the default branch, the WebView2 desktop game. Gameplay, cards,
  server, launcher and release builds live here.
- `html-main`: the browser-only HTML version. Shared changes are checked there
  before they are carried over; desktop-only changes are not.

## Design principles

- The board is always the visual centre; the UI serves the game.
- Every card should make a change you can see on the board.
- The engine always has a fallback, so older computers can still play.
- Smoke tests guard the rules; real screenshots check the look.

## Older notes

[Compatibility log 0.1.37](compatibility-0.1.37.md),
[maintenance 0.1.36](maintenance-0.1.36.md),
[desktop engine migration](desktop-engine-migration.md),
[refactor plan](refactor-plan.md), and [docs/archive](archive/).

## AI assistance

AI coding tools were used during development. The maintainer decides the
game direction, judges the experience, and owns testing and releases.
