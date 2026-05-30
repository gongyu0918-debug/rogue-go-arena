# Maintenance Refactor Loop

This plan keeps the current feature baseline stable while reducing the cost of future gameplay and UI changes.

## Guardrails

- Do not change gameplay behavior unless a smoke test exposes an existing bug and the fix is separately reviewed.
- Keep the legacy root UI playable until a React path reaches feature parity.
- Every 1-2 extraction steps must add or update a focused smoke test.
- Every broader slice must get an independent subagent review before commit.
- Commit only when the current baseline is cleaner and all relevant smoke tests pass.

## Current Split

- Gameplay rules and card effects live under `app/gameplay`; keep them server-agnostic and test them with direct smoke tests.
- Runtime adapter boundaries live under `app/runtime`; keep server globals behind explicit binding dataclasses.
- `server.py` is now the composition layer for FastAPI routes, global runtime state, and binding factories. New gameplay branches should not be added there directly.
- Shared runtime callback types live in `app/runtime/callback_types.py`; use these instead of redefining send or engine-command signatures in new adapters.
- `static/index.html` should stay as the stable legacy root while React preview work reaches feature parity.

## Next Decomposition Loop

1. Audit remaining `server.py` `_deps()` helpers.
   - Keep helpers that are active runtime or smoke-test boundaries.
   - Remove only duplicate helpers that no longer improve testability.
   - Smoke: impacted adapter smoke plus `runtime_smoke_test.py` when WebSocket or AI flow wiring changes.

2. Group WebSocket action dependencies.
   - Preserve `WebSocketActionContext`, but split card, board, AI, and setup dependencies into smaller value objects.
   - Smoke: `ws_context_smoke_test.py`, `ws_context_adapters_smoke_test.py`, and `websocket_endpoint_smoke_test.py`.

3. Finish backend composition cleanup.
   - Move thin binding construction into narrow runtime modules only when it reduces direct `server.py` imports or repeated wiring.
   - Smoke: target adapter smoke, then a live `/status` runtime smoke for server-level changes.

4. Continue React preview by vertical parity slices.
   - Protocol types, board shell, setup, cards/wiki, review/log.
   - Smoke: frontend build and screenshot checks at desktop, tablet, and mobile sizes before any root switch.

5. Release-readiness pass.
   - Verify installer/uninstaller language coverage, arbitrary install path, installed-app `/status`, root, `/card-editor`, and `/react-preview`.
   - Do not publish unless installed-path smoke and GitHub release asset checks both pass.

## Backend Slices

1. Move pure domain helpers out of `server.py`.
   - SGF export, scoring helpers, coordinate-only helpers.
   - Smoke: dedicated pure helper smoke (`sgf_smoke_test.py`, `rank_helpers_smoke_test.py`, `move_history_smoke_test.py`) plus `runtime_smoke_test.py` for exported SGF.

2. Move runtime environment helpers out of `server.py`.
   - Access URLs, GPU status, engine status payload shaping.
   - Smoke: `access_urls_smoke_test.py`, `gpu_info_smoke_test.py`, `status_payload_smoke_test.py`, `status_endpoint_smoke_test.py`, `startup_compat_smoke.py`, and `board_sync_smoke_test.py`.

3. Move remaining Rogue orchestration from `server.py`.
   - Activation, challenge loadout, post-move hooks.
   - Smoke: `capture_foul_smoke_test.py`, `turn_modifiers_smoke_test.py`, `card_smoke_test.py`, plus per-card WebSocket entry smoke when handlers move.

4. Move remaining Ultimate orchestration from `server.py`.
   - AI turn flow, force-score, quickthink end, special-card bridges.
   - Smoke: `ai_move_helpers_smoke_test.py`, `ultimate_helpers_smoke_test.py`, `card_smoke_test.py`, `runtime_smoke_test.py`, and Ultimate per-card smoke.

5. Reduce WebSocket handler coupling.
   - Keep `WebSocketActionContext`, but group dependencies into smaller service objects.
   - Smoke: full installed-app runtime smoke before release.

## Frontend Slices

1. Finish legacy extraction boundaries.
   - Move server event translation, wood select, review controls, and WebSocket dispatch out of `static/index.html`.
   - Smoke: `frontend/scripts/legacy-responsive-smoke.mjs`.

2. Add typed protocol contracts in the React preview path.
   - Match current WebSocket/API payloads without changing wire shape.
   - Smoke: React preview smoke and sampled live payload checks.

3. Migrate one vertical UI slice at a time.
   - Board shell, setup controls, card offers/wiki, review/log.
   - Smoke: screenshot-based Playwright checks at desktop, tablet, and mobile sizes.

4. Switch root only after parity.
   - Keep `/legacy` as a real fallback.
   - Smoke: installed build root, `/legacy`, `/card-editor`, `/react-preview`.

## Review Cadence

- Small pure extraction: local smoke is enough before commit.
- Runtime or WebSocket extraction: subagent review before commit.
- Frontend layout or user-flow extraction: subagent review plus screenshot smoke before commit.
- Release candidate: installed-app smoke and GitHub release metadata verification.
