# Card values (2026-10-13)

`value_points` in `app/data/cards.json` comes from this measurement. The AI
receives `CARD_KOMI_SHARE` of the value of the cards you hold as komi, capped
at `CARD_KOMI_MAX` per game; negative values count as 0. The run calibration
(docs/run-curve-calibration-20261013.md) set these to 100% and 60.

## Method

`tools/card_balance_eval.py --mode rogue --size 19 --level standard
--rogue-plies 120 --rogue-games 1`, in 7 parallel processes. For each card:
one 120-move game per colour and per player strategy (engine, guided), so 4
games; KataGo's score lead for the card holder at the end. The value is the
mean minus the no-card baseline (mean -1.1 over 28 games,
sd 6.0). Single games are noisy (about ±5 per card).

## Caveats

- The bot plays its moves instantly, so **Quick Think** earns its bonus move
  every turn (+363). Humans who play fast in easy positions can do the same;
  that is a real exploit worth fixing in the card, not just a measurement quirk.
- Cards that need a human plan (God's Hand's hidden point, Coach Login,
  Puppet, Last Stand) measure near 0 because the bot does not use them well.

## Values

| Card | Points |
|---|---|
| `quickthink` | +363.5 |
| `no_regret` | +81.0 |
| `dice` | +80.0 |
| `momentum` | +47.5 |
| `slip` | +30.5 |
| `handicap_quest` | +26.5 |
| `sanrensei` | +22.0 |
| `foolish_wisdom` | +19.5 |
| `attack_first` | +14.0 |
| `joseki_ocd` | +13.5 |
| `sansan_trap` | +13.5 |
| `exchange` | +13.0 |
| `nerf` | +12.5 |
| `capture_foul` | +12.0 |
| `twin` | +11.5 |
| `time_press` | +9.5 |
| `sprout` | +8.0 |
| `suboptimal` | +4.5 |
| `corner_helper` | +3.5 |
| `god_hand` | -0.5 |
| `last_stand` | -0.5 |
| `iron_wall` | -0.5 |
| `defense_first` | -2.0 |
| `five_in_row` | -2.0 |
| `methodical` | -2.0 |
| `puppet` | -2.5 |
| `capture_chain` | -3.0 |
| `coach_mode` | -3.5 |
