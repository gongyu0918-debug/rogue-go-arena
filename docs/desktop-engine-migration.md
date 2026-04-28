# Desktop Engine Migration

GoAI uses a WebView2-first desktop shell with the existing FastAPI server and KataGo kept as sidecar processes.

## Runtime Shape

```text
GoAI.exe
  starts/reuses GoAI_Server.exe on 127.0.0.1:8000
  opens WebView2 via pywebview
    loads http://127.0.0.1:8000/?rev=...
  falls back to Edge app-window, then system browser

GoAI_Server.exe
  serves static/index.html and assets
  owns WebSocket game state
  starts/stops KataGo backends as needed

katago/*.exe
  isolated GTP engines
  can crash or be stopped without taking down the desktop shell
```

## Why This Shape

- Keeps the HTML UI portable and close to the current browser implementation.
- Avoids putting GPU-heavy KataGo work inside the UI process.
- Lets the desktop shell manage startup, stale ports, and shutdown without changing game logic.
- Preserves browser-based smoke tests because the UI contract remains HTTP/WebSocket.

## Shell Selection

```bash
python launcher.py --shell webview
python launcher.py --shell edge
python launcher.py --shell browser
```

`webview` is the default. `GOAI_DESKTOP_SHELL=edge` or `GOAI_DESKTOP_SHELL=browser` can override it for diagnostics.

## Smoke Checklist

- `python -m compileall launcher.py server.py app`
- `python card_smoke_test.py`
- `python runtime_smoke_test.py --base-url http://127.0.0.1:8000`
- Open the installed `GoAI.exe` and confirm the WebView2 shell stays alive.
- Browser-check `http://127.0.0.1:8000` for UI regressions and console errors.
