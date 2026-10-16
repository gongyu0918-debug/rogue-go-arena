# Balance update 0.1.42 (2026-10-16)

Keeps the komi-based approach. Goals: a friendlier opening, a difficulty
setting that weak players can actually win on, and no Quick Think exploit.
Scoring is unchanged (KataGo final_score); komi is still only set at game
start and at card pick (plus the existing Erosion card).

## What changed

| Constant | Old | New |
|---|---|---|
| `CARD_KOMI_MAX_STAGE1` (new) | (flat 60) | 15 |
| `CARD_KOMI_MAX_STAGE2` (new) | (flat 60) | 25 |
| `CARD_KOMI_MAX_STAGE3` (new) | (flat 60) | 35 |
| `CARD_KOMI_MAX_STAGE4` (new) | (flat 60) | 50 |
| `CARD_KOMI_MAX_STAGE5` (new) | (flat 60) | 60 |
| `CARD_KOMI_MAX` | 60, the only cap | 60, now the overall ceiling (kept so saved editor configs still load) |
| `RUN_STAGE1_KOMI_POINTS` | 10 | 0 |
| `RUN_STAGE2_KOMI_POINTS` | 15 | 5 |
| `DIFFICULTY_BEGINNER_POINTS` | -20 | -40 |
| `DIFFICULTY_EASY_POINTS` | -10 | -25 |
| `ROGUE_QUICKTHINK_COOLDOWN_TURNS` (new) | (every turn) | 5 |
| `ROGUE_QUICKTHINK_MAX_BONUS` (new) | (no cap) | 4 |
| Quick Think `value_points` | 363.5 | 67 |

All new constants are tunable in the card editor. Quick Game uses the stage 1
card-komi cap. The stage curve before cards is now about 0 / 5 / 31 / 50 / 78
points (was 10 / 15 / 31 / 50 / 78); the worst stage 1 opening komi on Normal
is -7.5 (was -62.5 with a strong card).

Smaller boards: the curve is tuned for 19x19. On 9x9 and 13x13 every point
value (stage, difficulty, cards) scales with board area and the stage's
stones become komi; each stage still gets harder (19x19: 0 / 5 / 31 / 50 /
78, 13x13: 0 / 2.5 / 14.5 / 23.5 / 36.5, 9x9: 0 / 1 / 7 / 11 / 17.5 before
cards).

Quick Think: the bonus window opens at most every 5th player turn and at most
4 times per game; turns without a window have no 2-second pressure. All
arming points go through `app/gameplay/quickthink_window.py`.

Installer: removes leftover `model_large` / `model_b18` when the build does
not ship them (the engine picked the old model over the shipped one), removes
the legacy-named `katago.exe` when the CUDA upgrade's `katago_cuda.exe`
replaces it, no longer creates empty `_test` / `_downloads` folders, and
removes the two left by 0.1.41. The optional CUDA upgrade pack and the CPU
fallback are kept. The build script now requires `katago_cpu.exe` (the 0.1.41
installer shipped without it).

## Method

`tools/run_curve_eval.py`, 25 games per cell, 200 moves, KataGo score at the
end (lead > 0 = win). The AI plays at the standard strength (200 visits).
"Before" runs use the same code with the old values through `--set`.

- Player strength: `standard` (same as the AI), `10k` (60 visits, a casual
  player) or `18k` (2 visits, a weak player). Even 2-visit KataGo is far
  stronger than a real beginner, so treat the weak-player numbers as an upper
  bound on how a human fares.
- Runs: decks drawn through the real challenge offers. Stages 3 to 5 use
  paired decks (the same seed gives the same decks before and after);
  stages 1 and 2 were run before the pairing fix and are unpaired.
- Quick Think: `--quick-card quickthink`, Quick Games on Normal, colours
  alternating, your side moving instantly (the worst case).

Single games vary a lot (30 to 60 points), so a 25-game win rate is roughly
±10 percentage points.

## Results

### Weak and casual players, run stage 1

| Player | Difficulty | Before | After |
|---|---|---|---|
| 18k (2 visits) | Beginner | 36% | 72% |
| 18k (2 visits) | Easy | 20% | 72% |
| 18k (2 visits) | Normal | 24% | 28% |
| 10k (60 visits) | Easy | 72% | 88% (Easy at -10; -25 is easier still) |
| 10k (60 visits) | Normal | 28% | 56% |

The tuned Beginner/Easy values were picked from intermediate cells: with the
new caps but the old difficulty values, the 18k player won 64% on Beginner
(-20) and 40% on Easy (-10).

### Same-strength player across the run (Normal)

| Stage | Before | After | Target before / after |
|---|---|---|---|
| 1 | 44% | 80% | 19 / 9 |
| 2 | 52% | 68% | 37 / 22 |
| 3 | 40% | 60% | 63 / 56 |
| 4 | 72% | 60% | 90 / 87 |
| 5 | 68% | 76% | 128 / 128 |

Stages 1 to 3 are clearly friendlier, as intended. Stage 4 differs only by its
card cap (60 before, 50 after), so before should not be harder; the gap is
within the noise of 25 games. Stage 5 settings are identical before and after
(cap 60, same stage komi), so its 68% vs 76% is pure noise: two 25-game samples
of the same settings landed 8 points apart.

### Quick Think (Quick Game, Normal, lead after its 15-point charge)

| Setting | Games | Mean lead |
|---|---|---|
| uncapped (before) | 26 | +367 |
| window every 4 turns, max 8 | 13 | +119 |
| window every 5 turns, max 4 (chosen) | 25 | +51 |
| window every 6 turns, max 3 | 11 | +30 |

The chosen setting puts the card at about +67 points (lead + charge +
baseline), the tier of No Regrets (+81) and Dice (+80).

## Not done / open

- The weak-player proxy is still much stronger than a human beginner; the
  difficulty values need real playtesting.
- Normal stays at 0 (it anchors the run curve): 28% for the 2-visit player,
  56% for the 60-visit player.
- Late stages (4 and 5) are now easier than before for a same-strength
  player (60 to 76% wins); the stage curve there was not changed.
- No installer was built; the installer changes were checked with `ISCC /O-`
  (compile without output) and the preprocessed script.
