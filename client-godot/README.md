# rogue-go-arena Godot client

This is the native desktop client track for rogue-go-arena 1.0.

Runtime shape:

```text
Godot window
  draws board, UI, cards, animations
  starts go_runtime_worker.py over stdin/stdout JSON lines

go_runtime_worker.py
  owns game state and card logic
  starts and stops KataGo when AI play is needed
  exposes no HTTP server and opens no TCP port
```

Development notes:

- Open this folder with Godot 4 C#.
- The current scene is a WebView-replica scaffold with the same wood shell,
  command deck, board HUD, toolbar labels, card icon tray, and side console
  skeleton. Keep copying the existing UI before any later redesign.
- The worker uses the repository `.venv\Scripts\python.exe` when present.
- Godot assets live under `client-godot/assets` and are copied from the existing
  `static/assets` visual set. Do not package `static/index.html`, `static/js`, or
  the legacy WebView runtime into the Godot client.
- The scene must stay responsive: large displays show the side console, narrow
  displays prioritize a centered board with compact toolbar icons.
- The exported 1.0 client must bundle the worker and Python runtime before release.
