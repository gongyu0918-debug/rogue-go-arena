# Changelog

## 0.1.42 (2026-10-16)

Balance (details and self-play numbers in docs/balance-update-20261016.md):
- Card komi cap grows with the stage: 15 / 25 / 35 / 50 / 60 (was a flat 60);
  Quick Game uses the stage 1 cap. The opening komi is no longer scary.
- Stage 1 and 2 komi lowered to 0 and 5 (was 10 and 15); each stage still
  gets harder.
- Beginner and Easy are easier: -40 and -25 points for the AI (was -20 and
  -10). A weak sparring player now wins about 72% of stage 1 runs on both.
- On 9x9 and 13x13 boards all komi values scale with board area and stage
  stones become komi.
- Quick Think: the bonus window opens at most every 5th turn and 4 times per
  game (it opened every turn, worth about +367 points to a fast player).

Installer:
- Removes leftover KataGo models the build does not ship (they overrode the
  shipped model) and the legacy-named CUDA engine when the CUDA upgrade
  replaces it; keeps the optional CUDA upgrade pack and the CPU fallback.
- No more empty `katago\_test` / `katago\_downloads` folders; the ones left by
  0.1.41 are removed.
- The build now requires the CPU fallback engine `katago_cpu.exe`.

Tools:
- `tools/run_curve_eval.py`: `--player-level` (weaker sparring player),
  `--set KEY=VALUE` overrides, `--quick-card` (Quick Games), paired decks
  across before/after runs. `tools/card_balance_eval.py`: `--set`.

## 0.1.41 (2026-10-13)

- Ultimate mode archived behind `ULTIMATE_ENABLED`.
- One fixed standard AI strength (200 visits); ranks only under Advanced in
  normal games.
- Difficulty selector; 5-stage runs on a komi and handicap-stone curve;
  card-strength komi from measured card values; target display in card
  games; AI rally off by default.
- Readable card pick screen with consistent card art.
