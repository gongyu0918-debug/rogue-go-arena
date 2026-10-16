# Run curve calibration (2026-10-13)

> **Superseded in part (0.1.42):** stage 1/2 komi, the card-komi cap and the
> Beginner/Easy values changed; see docs/balance-update-20261016.md.

Goal: a run should not snowball. As cards pile up stage by stage, the AI's
head start (stage stones and komi plus card komi) should grow with them, so a
typical deck's result stays level from stage 1 to stage 5.

## Method

`tools/run_curve_eval.py`: for each stage, typical decks drawn through the
real challenge offers (one random pick from each offer of three), the stage
set up exactly like the server (AI stones, stage komi, card komi, loadout),
and a 200-move game where KataGo plays your side at the same standard
strength as the AI (engine strategy). Result = your final lead by KataGo's
score (positive = you win). Games vary a lot (sd 30 to 60 points), so read
the trend, not single stages.

Because the test player is as strong as the AI, the absolute level says
little about human players; the difficulty setting covers that and needs
playtesting. What the pass checks is the slope across stages.

## Before (card komi 50%, cap 15; stage curve about 0/5/10/17/28)

| Stage | Target | Mean lead | Wins |
|---|---|---|---|
| 1 | 8 | +37 | 5/6 |
| 2 | 16 | +84 | 5/6 |
| 3 | 23 | +60 | 5/6 |
| 4 | 32 | +135 | 3/3 |
| 5 | 43 | +158 | 6/6 |

Slope +28.7 points per stage: each extra card added about 29 points, the
curve about 9. Over 200-move games with a deck, cards are worth roughly two
to three times their single-card 120-move measurement, and the 15-point cap
stopped charging after the second card.

## After (card komi 100%, cap 60; stage curve about 10/30/46/60/88)

| Stage | Target | Mean lead | Median | Wins |
|---|---|---|---|---|
| 1 | 26 | -4 | -1 | 2/5 |
| 2 | 61 | -24 | -20 | 0/5 |
| 3 | 84 | -26 | -36 | 1/5 |
| 4 | 90 | -4 | -18 | 2/5 |
| 5 | 132 | +5 | -27 | 2/5 |

Slope +3.7 points per stage: the snowball is gone. Overall mean -10.6, a bit
tough mid-run, so the final table moves stages 2 to 5 back toward the player
by 10 to 15 points (a linear correction from these games).

## Final table verified (25 more games)

| Stage | Target | Mean lead | Median | Wins |
|---|---|---|---|---|
| 1 | 15 | -3 | -9 | 2/5 |
| 2 | 28 | -13 | -13 | 0/5 |
| 3 | 77 | -3 | -29 | 2/5 |
| 4 | 90 | 0 | -23 | 2/5 |
| 5 | 133 | +5 | -9 | 2/5 |

Slope +3.0 points per stage (flat). Overall mean -2.6, median -11.7, 8 of 25
wins: a few decks blow out, most games end narrowly against the player. For
an AI-strength player the typical run is slightly tough; real players are
weaker, so the difficulty setting needs human playtesting.

## Final values

| Stage | AI stones | Stage komi | About, before cards |
|---|---|---|---|
| 1 | 0 | 10 | 10 |
| 2 | 0 | 15 | 15 |
| 3 | 2 | 10 | 31 |
| 4 | 3 | 15 | 50 |
| 5 | 5 | 15 | 78 |

Card komi: `CARD_KOMI_SHARE` 1.0, `CARD_KOMI_MAX` 60. Worst-case komi (Hard,
stage 5, maxed cards) is -84.5. Every value is tunable in the card editor.
