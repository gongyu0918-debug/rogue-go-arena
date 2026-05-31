# rogue-go-arena Refactor Plan

This project is stable enough to play, but the codebase has two high-risk growth points:

- `static/index.html` has been acting as the UI shell, WebSocket client, board renderer, i18n layer, and card UI host.
- `server.py` still owns HTTP routes, WebSocket dependency wiring, AI move orchestration, Rogue effects, Ultimate effects, scoring helpers, and KataGo-dependent orchestration.

The goal is controlled extraction, not a broad rewrite. Every step should leave the app runnable and covered by smoke tests.

## Architecture Direction

The long-term target is a React + TypeScript frontend, but the rewrite is a parallel migration, not a forced replacement:

- Keep the current classic-script frontend as the stable production root until the React path reaches feature parity.
- Serve the React app at `/react-preview`, build it into `static/react/`, and leave root and `/card-editor` untouched during preview work.
- Use React for UI composition and state ownership, and keep Canvas as the board rendering surface. Do not introduce a large game engine for the board.
- Use typed reducers and protocol contracts for game, WebSocket, card, and UI state. Avoid new implicit globals.
- Move behavior by vertical slices: board shell, WebSocket contracts, game state, cards/setup/review/log, then root switch only after smoke parity.
- Keep old frontend modules readable and tested while React migrates. The fallback path must remain useful, not become dead code.

## Compatibility And Performance Policy

Future maintainability and performance are the default decision criteria, bounded by the old-PC promise in the README:

- Runtime browser target: Edge/WebView2 109 compatibility is the lowest practical desktop-web target because Windows 7/8/8.1 stopped at Edge/WebView2 109. The Vite build must stay configured for `chrome109` / `edge109` unless README support is intentionally changed.
- No dependency may assume a newer browser-only API without either a compile transform or an explicit fallback. Examples to review before use: WebGPU, File System Access, OffscreenCanvas-only flows, SharedArrayBuffer, top-level browser APIs not present in Chromium 109.
- Optimize for the current board interaction profile: small React state updates for UI, direct Canvas drawing for high-frequency board rendering, stable event handlers, and no unnecessary re-rendering during hover/fine-tune movement.
- Prefer proven, small dependencies. A community package must either reduce code risk materially or become a test oracle; it should not replace a stable custom subsystem just because it exists.
- Community Go libraries are advisory first: `goban-engine` can be used for replay/legal-move oracle tests if the spike proves value; `@sabaki/sgf` can replace SGF parsing only after golden tests; renderer/player packages are references, not direct replacements.
- Keep the Python backend authoritative for rules, Rogue/Ultimate effects, AI move orchestration, and scoring. Frontend helpers may preview or validate, but must not become a second source of truth.
- Release builds must run the frontend build before PyInstaller/Inno, and installer smoke must verify the built static output on the installed app path before publish.

## Workspace Policy

- Primary development workspace: `F:\Workspaces\rogue go project\rogue-go-arena`
- Playground repo path: `F:\Workspaces\Playground\projects\apps\rogue-goai`
- Treat Playground as source/publish/sync history. Do new implementation work in the primary workspace, then sync intentionally.

## Current Frontend Split

Done:

- `static/js/rogue_cards_ui.js`
  - Rogue card offer modal
  - Ultimate card offer modal
  - Rogue/Ultimate card wiki rendering
  - Rogue skill button binding and display state
  - Ultimate status bar rendering
- `static/js/card_catalog.js`
  - Card id lists
  - Card presentation metadata
  - Localized card lookup
  - Safe card icon/meta markup helpers
- `static/js/card_board_marks.js`
  - Rogue seal/blackhole/golden-corner/fog board overlays
  - Ko marker
  - Joseki/puppet/Ultimate target markers
  - AI Rogue seal overlays
- `static/js/card_state.js`
  - Rogue/Ultimate card offer state
  - Active Rogue/AI card state
  - Rogue seal/uses/puppet state
  - Ultimate selection state
  - Card turn timer state
- `static/js/card_turn_timer.js`
  - Rogue Quick Thinking countdown
  - Ultimate Quick Thinking countdown
  - Card turn timer cleanup and UI refresh
- `static/js/board_layout.js`
  - Board canvas element/context ownership
  - Stage preset sizing
  - Canvas DPR sizing and CSS fit variables
  - Board recovery/watchdog helpers
- `static/js/board_assets.js`
  - Board and stone texture loading
  - Board visual cache invalidation
  - Board base texture painting
  - Stone sprite cache and texture painting
- `static/js/board_renderer.js`
  - Board grid, star points, stones, and move numbers
  - Hint and review-hint drawing
  - Territory overlay drawing
  - Main canvas render pass
- `static/js/board_input.js`
  - Board coordinate conversion
  - Pointer/touch hover and placement handling
  - Fine-tune placement state and controls
  - Player move commit and AI response timeout
- `static/js/i18n.js`
  - Language detection and persistence
  - Locale pack loading and fallback lookup
  - `ui`, `escapeHtml`, object-locale, and rank label helpers
  - Language switching entry point
- `static/js/shell_ui.js`
  - Generic text/title helpers
  - Connection indicator and top HUD synchronization
  - Engine status localization
  - Toolbar sound/territory visuals and quick actions
- `static/js/game_log.js`
  - Game log entry storage
  - Localized log append helpers
  - Server event log bridge
  - Log rendering and clearing
- `static/js/server_event_i18n.js`
  - Server event translation tables for legacy logs and card-effect banners
  - Chinese passthrough and English/Japanese/Korean pattern translations
- `static/js/wood_select.js`
  - Custom select enhancement, popover placement, and menu close behavior
  - Shared `syncWoodSelect`, `syncWoodSelects`, and `closeWoodSelectMenu` globals used by legacy modules
- `static/js/review_controls.js`
  - Local review board replay helpers used by the legacy renderer
  - SGF import/export, review navigation, keyboard shortcuts, and review analysis requests
- `static/js/localization_ui.js`
  - Legacy language select bindings and `applyLanguage` refresh flow
  - Localized shell, settings, overlay, setup option, and runtime view labels
- `static/js/websocket_messages.js`
  - Legacy WebSocket message dispatch table
  - Named handlers for game state, analysis, Rogue, Ultimate, reconnect, and error messages
- `static/js/app_bootstrap.js`
  - Legacy WebSocket connection setup
  - Startup sequence and board recovery/resize hooks
- `static/js/setup_controls.js`
  - Setup modal, mode selection, and new-game payload wiring
  - Setup row visibility, mode hints, time, Rogue variant, and stage preset controls
- `static/js/settings_controls.js`
  - Settings drawer toggles, sound control, level/handicap setup bindings
  - Card editor modal entry point
- `static/js/runtime_status_ui.js`
  - Thinking indicator, game-over overlay, score/reason text, runtime info panel, and winrate history UI
- `static/js/game_timers.js`
  - Game timer state, absolute/byoyomi countdowns, display refresh, and timeout dispatch
- `static/js/visual_effects.js`
  - Sound state, stone/capture animations, board intro/ripples, overlay sparks, and card-effect visual bursts
- `static/js/network_client.js`
  - `/status` refresh, network status cache, shell sync, and shared WebSocket JSON send helper
- `static/js/game_runtime_helpers.js`
  - Challenge-session state, current board/size helpers, and board diff detection for move animations
- `static/js/toolbar_actions.js`
  - Main in-game toolbar actions for pass, undo, score, and resign
  - Shared toolbar button enable/disable state
- `static/js/inline_actions.js`
  - Top quick actions, modal closes, setup mode buttons, settings drawer open/close, and overlay shortcuts
  - Replaces remaining inline `onclick` markup handlers
- `static/js/rank_controls.js`
  - Rank select population, GPU default rank, and slow-rank warnings
  - Shared rank-label refresh used by localization
- `static/js/legacy_state.js`
  - Legacy global constants and mutable runtime state used by classic scripts
  - Game id persistence, rank labels, board defaults, player colors, and analysis defaults
- `static/js/legacy_entry.js`
  - Classic frontend startup sequence
  - Rogue skill binding, rank initialization, bootstrap hooks, and app boot
- `static/legacy.css`
  - Legacy root page visual system and responsive layout
  - Board shell, toolbar, modals, wiki, setup, settings, and HUD styling

Still in `static/index.html`:

- Static markup and script loading order for the legacy root page

## Frontend Extraction Roadmap

1. React scaffold and preview route
   - `frontend/` owns Vite, React, TypeScript, and typed source.
   - `static/react/` is generated output served by `/react-preview`.
   - Review the package static collection path before release changes.

2. Frontend protocol contracts
   - Add TypeScript unions for WebSocket actions/messages and card-config API payloads.
   - Validate contracts against sampled live payloads; do not change wire shape.

3. React board shell
   - Move Canvas board layout, renderer, and input into typed React modules.
   - Keep Canvas drawing imperative and minimize React updates on pointer move.
   - Verify desktop/mobile nonblank canvas and coordinate probes.

4. React state and WebSocket client
   - Add reducers for connection, game state, thinking/analysis, log, and card UI.
   - Split `ws_client` transport from message handlers.
   - Real runtime smoke is required because this touches move flow.

5. React cards/setup/review/log
   - Migrate Rogue/Ultimate offers, active card HUD, wiki, setup controls, SGF/review, and game log.
   - Preserve XSS-safe text rendering for all card config strings.
   - Keep the card editor route independent until it is migrated deliberately.

6. Dependency spikes
   - Test `goban-engine` and optional `@sabaki/sgf` in isolated preview/test modules.
   - Keep only dependencies that pass size, compatibility, and behavior checks.
   - If a dependency is unstable or too heavy, preserve the custom typed implementation and add golden tests.

7. Legacy fallback and root switch
   - Switch `/` to React only after feature parity smoke passes.
   - Move old `static/index.html` to `/legacy` as a real fallback.
   - Do not delete the legacy route until installed builds prove the React path on old and current machines.

## Backend Extraction Roadmap

1. `app/gameplay/rogue_effects.py`
   - Move player Rogue effect activation and per-move hooks.
   - Keep functions pure where possible: input `GoGame`, return effect result.
   - Coach-mode AI takeover flow now lives in `app/gameplay/coach_mode.py`.
   - Challenge set message/engine synchronization flow now lives in `app/gameplay/challenge_flow.py`.
   - Capture-foul event emission and komi synchronization now live in `app/gameplay/capture_foul_flow.py`.
   - Rogue/Ultimate five-in-row and last-stand trigger orchestration now lives in `app/gameplay/line_trigger_flow.py`.

2. `app/gameplay/ultimate_effects.py`
   - Move `_apply_ultimate_effect`, `_ultimate_ai_move`, `_ultimate_force_score`.
   - Avoid adding new Ultimate branches in `server.py`.

3. `app/gameplay/ai_moves.py`
   - Move AI move selection variants: avoid points, no-resign retry, suboptimal, style generation.
   - KataGo command, board-sync, komi-sync, and analysis adapters now live in `app/runtime/engine_gateway.py`.
   - AI observer self-play loop now lives in `app/gameplay/ai_observer.py`.
   - Runtime game-visit policy now lives in `app/runtime/game_visits.py`; `server.py` only supplies current CPU-mode state.
   - Continue moving AI turn branches behind the existing `AiMoveService` and engine gateway instead of adding direct `engine.*` calls in `server.py`.

4. `app/runtime/ws_handlers.py`
   - WebSocket session lifecycle and dispatch now live in `app/runtime/ws_session.py`.
   - WebSocket route registration now lives behind `app/runtime/ws_routes.py`; `server.py` only supplies current session/runtime bindings.
   - Continue moving action dependencies out of `server.py` without changing wire payloads.
   - Preserve the current `WebSocketActionContext` direction; expand it instead of passing many globals.
   - WebSocket context group and field inventories are derived from dependency dataclasses to avoid hand-maintained drift.
   - `/gpu` payload detection, caching, CPU-mode override, and model-file flag orchestration now live in `app/runtime/gpu_info.py`.
   - Static page route registration now lives behind `app/runtime/static_page_routes.py`; `server.py` only supplies the current static directory binding.
   - Rank and engine-control route registration now lives behind `app/runtime/control_routes.py`; `server.py` only supplies current runtime bindings.
   - Status, GPU, and SGF export route registration now lives behind `app/runtime/info_routes.py`; `server.py` only supplies current runtime bindings.

5. `app/services/card_config_service.py`
   - Move live card config reload/save/reset orchestration out of `server.py`.
   - Card config and balance API routes now live behind `app/runtime/config_routes.py`; `server.py` only supplies the current binding.
   - Introduce per-game config snapshots so editing cards affects new games, not active games.

## Anti-Sprawl Rules

- No new feature should add another 100+ lines to `static/index.html` or `server.py` unless it is temporary and immediately followed by extraction.
- New card UI belongs in `static/js/rogue_cards_ui.js` or a narrower card module.
- New board drawing for card effects belongs in `static/js/card_board_marks.js`.
- New Rogue/Ultimate server logic belongs in gameplay modules, not directly in `server.py`.
- Prefer data-driven entries in `app/data/cards.json` and tuning values over hard-coded branches.

## Verification Gates

For frontend card/UI changes:

- `python card_smoke_test.py`
- `python card_editor_effect_smoke.py`
- Browser/Playwright check for card editor and offer modal rendering.

For gameplay or AI changes:

- Real server runtime smoke: `python runtime_smoke_test.py --base-url http://127.0.0.1:<port>`
- Verify the server uses a real KataGo backend when the change touches AI flow.

For releases:

- Build installer.
- Install into `F:\rogue-go-arena`.
- Verify installed server `/status`, `/card-editor`, root page, and installer hash.
