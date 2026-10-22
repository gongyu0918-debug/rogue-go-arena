# Changelog

## 0.1.43 (2026-10-22)

Balance (details and self-play numbers in docs/balance-update-20261020.md):
- Late run stages stay close: stage 3 komi 30 (was 10), stage 4 has 4 stones
  and 27 komi (was 3 and 15), stage 5 has 7 stones and 30 komi (was 5 and
  15). A same-strength player now wins about half of stages 3 to 5, with mean
  leads of +2, +5 and -5 (was +26, +31 and +56).
- Rogue mode charges the AI 90% of the card's measured Rogue-mode value, up
  to 150 (was at most 15). The new per-card `rogue_points` covers the 11
  cards whose Rogue-mode worth differed from `value_points` (No Regrets 135.5,
  Momentum 82.5, ...). Average lead per card fell from +18.9 to +2.1, and
  games won by 30+ from 38% to 8%.

Display:
- Chinese-rules scores show stones (子), strictly half the point difference
  (7.5 points = 3.75子). The rules come from the game, no longer guessed from
  komi 7.5.
- Resignation and timeout results read "wins by resignation" / "wins on time"
  (中盘胜 / 超时胜) instead of "R子" / "T子".
- Card picker: three separate, same-size cards (no outer frame); "How it
  works" opens over the card, so the card keeps its size.

Tools:
- `tools/run_curve_eval.py --quick-card none` plays Rogue-mode games without
  a card, as a baseline.

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
