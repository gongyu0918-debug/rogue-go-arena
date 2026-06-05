# Native Godot Client

`desktop/no-port-1.0` moves rogue-go-arena toward a normal desktop game client.

## Boundary

- Godot owns the window, drawing, input, HUD, cards, animation, and packaged assets.
- Python worker owns current Go rules, Rogue/Ultimate cards, SGF, and KataGo orchestration.
- KataGo is always launched through the runtime engine wrapper and stopped on shutdown.
- No FastAPI, uvicorn, browser WebSocket, or local TCP listener is required for the native client path.
- `client-godot/assets` contains the native-client visual package copied from
  the existing `static/assets` textures and icons. The Godot package must not
  include legacy HTML, JavaScript, WebView cache, or browser runtime files.
- The Godot UI must replicate the current WebView UI first: existing Chinese
  copy, wood shell, board/stones, card icons, toolbar icon order, HUD labels,
  setup/status language, and overlay hierarchy are the source of truth until a
  later redesign is explicitly approved.
- Layout must remain responsive across laptop, 1080p, 1440p, 4K, windowed, and
  narrow displays. Large displays can show the side console; narrow displays
  should prioritize a centered board and compact icon toolbar.

## Current Milestone

- `go_runtime_worker.py` provides stdin/stdout JSON-line commands.
- `DesktopRuntimeSession` reuses existing action handlers without HTTP.
- `client-godot` contains a Godot 4 C# replica scaffold using copied
  `static/assets` textures/icons: wood background, board/stones, command deck,
  match HUD, toolbar, card icon tray, and side console skeleton.

## Next Milestones

1. Expand Godot board to 19x19, review hints, territory, fog, seal marks, and card effects while preserving WebView visuals.
2. Move setup, card offer, status bars, log, SGF, and editor surfaces into Godot `Control` scenes with matching copy/layout before redesign.
3. Bundle the Python worker and KataGo assets into the Windows installer.
4. Replace the main installer launcher with the Godot executable after real runtime smoke passes.
