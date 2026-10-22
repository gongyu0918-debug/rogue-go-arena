# Balance update (2026-10-20)

Feedback: late games were too easy, ending 30+ points ahead. This keeps the
komi-based approach and tightens both card modes:

- Runs (Challenge): stages 3 to 5 give the AI more stones and komi.
- Rogue mode (one card, one game): the AI is charged most of the card's
  measured Rogue-mode value instead of at most 15 points.

The same change shows Chinese-rules scores strictly in stones (子).

## What changed

| Constant | Old | New |
|---|---|---|
| `RUN_STAGE3_KOMI_POINTS` | 10 | 30 |
| `RUN_STAGE4_AI_STONES` | 3 | 4 |
| `RUN_STAGE4_KOMI_POINTS` | 15 | 27 |
| `RUN_STAGE5_AI_STONES` | 5 | 7 |
| `RUN_STAGE5_KOMI_POINTS` | 15 | 30 |
| `ROGUE_CARD_KOMI_SHARE` (new) | (Rogue mode used `CARD_KOMI_SHARE` 1.0) | 0.9 |
| `ROGUE_CARD_KOMI_MAX` (new) | (Rogue mode used `CARD_KOMI_MAX_STAGE1` 15) | 150 |

The run curve before cards is now about 0 / 5 / 51 / 76 / 121 points (it
was 0 / 5 / 31 / 50 / 78). Stages 1 and 2 are unchanged.

### Rogue-mode card values

New per-card field `rogue_points`: what the card is worth in Rogue mode.
Rogue mode charges `ROGUE_CARD_KOMI_SHARE × rogue_points`, falling back to
`value_points`, up to `ROGUE_CARD_KOMI_MAX`. Runs still use `value_points`
and the stage caps.

| Card | `value_points` | `rogue_points` | Rogue-mode charge, old → new |
|---|---|---|---|
| No Regrets | 81 | 135.5 | 15 → 122 |
| Momentum | 47.5 | 82.5 | 15 → 74 |
| Slip | 30.5 | 57.5 | 15 → 52 |
| Quick Think | 67 | 54.5 | 15 → 49 |
| Foolish Wisdom | 19.5 | 50.5 | 15 → 45.5 |
| Five in a Row | -2 | 36 | 0 → 32.5 |
| God's Hand | -0.5 | 32.5 | 0 → 29 |
| Time Press | 9.5 | 32.5 | 9.5 → 29 |
| Attack First | 14 | 31 | 14 → 28 |
| Corner Helper | 3.5 | 26 | 3.5 → 23.5 |
| Last Stand | -0.5 | 13.5 | 0 → 12 |

The other cards keep `value_points`. Charges over 15 rise to 90% of the
value: Dice 72, Handicap Quest 24, Sanrensei 20. Charges under 15 drop by
about 10%.

The share of 0.9 is deliberate. A strong card still leaves a small edge
(No Regrets about +13, Momentum +8), so the card feels good without
deciding the game.

## Scoring display

Under Chinese rules, results, the live lead and the territory line show
stones (子 / stones / 자 / Steine / pierres): half the point difference, so
a 7.5-point win shows as 3.75子. Japanese and other rules keep points.

The rules now come from the game's actual `rules` setting. They used to be
guessed from komi 7.5, which broke whenever handicap, difficulty or card
komi moved the komi.

Resignation and timeout results (`B+R`, `W+T`) read as 中盘胜 / 超时胜
("wins by resignation" / "wins on time") instead of "R子" / "T子".

## Method

`tools/run_curve_eval.py`, 200 moves, KataGo score at the end (lead > 0
means the player wins). The player is a same-strength bot (standard, 200
visits, same as the AI). Difficulty is Normal.

- Runs: decks drawn through the real challenge offers, 25 games per stage.
  Stages 4 and 5 use the paired seeds from the 0.1.42 runs (4041-4043,
  5051-5053), so the decks match; stage 3 is unpaired (3031-3033).
- Rogue mode: `--quick-card CARD`, colours alternate, every offerable card.
  - The new `--quick-card none` plays the same games without a card: 16
    games, mean -0.2, so the setup itself is level.
  - Measurement pass: 8 games per card.
  - Recalibrated cards: a second pass of 8 more (No Regrets 16), pooled.
    A card was recalibrated when its lead was at least 5 points and 1.5
    standard errors off the target.
  - Final check with the pooled values: 8 games per recalibrated card,
    16 for No Regrets.
- "Before" for Rogue mode: every played game is re-priced with the old
  charge. Its margin (lead + charge) is the card's worth in that game,
  whatever the charge was.

## Results

### Runs, same-strength player, Normal

| Stage | Before (0.1.42): wins / mean lead | After: wins / mean lead / median |
|---|---|---|
| 3 | 60% / +26.4 | 48% / +1.6 / -3.4 |
| 4 | 60% / +31.2 | 40% / +5.3 / -18.8 |
| 5 | 76% / +56.1 | 48% / -5.1 / -15.4 |

### Rogue mode, same-strength player, Normal (each card counts once)

| | Before | After |
|---|---|---|
| Average lead per card | +18.9 | +2.1 |
| Median game | +19.1 | +0.9 |
| Games won by 30+ | 38% | 8% |
| Player wins | 82% | 54% |
| Cards whose mean lead is within ±15 | 17 / 28 | 24 / 28 |
| Mean distance of a card's lead from 0 | 20.4 | 5.2 |

The biggest offenders before were No Regrets (+111.5), Dice (+72.9),
Momentum (+65.7) and Slip (+46.8). After the change:

| Card | Mean lead after |
|---|---|
| No Regrets | -8.9 |
| Momentum | +2.6 |
| Quick Think | +4.1 |
| Five in a Row | +0.8 |
| Slip | +18.6 |
| Dice | +15.9 |
| Foolish Wisdom | +15.5 |
| Methodical | -15.8 |

## Caveats

- Single games vary a lot: a standard deviation of 15 to 60 points, and No
  Regrets is the widest at about 60. An 8-game mean is roughly ±5 to ±20
  points.
  - Slip, Foolish Wisdom and Dice still look a little generous, but within
    the noise.
  - Methodical measures negative for the bot. Its charge is 0, so it
    cannot be helped through komi.
- Timing-sensitive cards measured differently from pass to pass, probably
  because of engine load from parallel jobs. Time Press went +42, +23,
  then +30.
- The player bot is far stronger than most humans, and it plays Quick Think
  instantly (the best case). The difficulty setting still covers human
  skill.
- No installer was built and nothing was released.
