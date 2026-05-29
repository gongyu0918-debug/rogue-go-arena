# Maintenance Refactor Loop

This plan keeps the current feature baseline stable while reducing the cost of future gameplay and UI changes.

## Guardrails

- Do not change gameplay behavior unless a smoke test exposes an existing bug and the fix is separately reviewed.
- Keep the legacy root UI playable until a React path reaches feature parity.
- Every 1-2 extraction steps must add or update a focused smoke test.
- Every broader slice must get an independent subagent review before commit.
- Commit only when the current baseline is cleaner and all relevant smoke tests pass.

## Backend Slices

1. Move pure domain helpers out of `server.py`.
   - SGF export, scoring helpers, coordinate-only helpers.
   - Smoke: dedicated pure helper smoke plus `runtime_smoke_test.py` for exported SGF.

2. Move runtime environment helpers out of `server.py`.
   - Access URLs, GPU status, engine status payload shaping.
   - Smoke: `access_urls_smoke_test.py`, `status_endpoint_smoke_test.py`, and `startup_compat_smoke.py`.

3. Move remaining Rogue orchestration from `server.py`.
   - Activation, challenge loadout, post-move hooks.
   - Smoke: `card_smoke_test.py` plus per-card WebSocket entry smoke when handlers move.

4. Move remaining Ultimate orchestration from `server.py`.
   - AI turn flow, force-score, quickthink end, special-card bridges.
   - Smoke: `card_smoke_test.py`, `runtime_smoke_test.py`, and Ultimate per-card smoke.

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
