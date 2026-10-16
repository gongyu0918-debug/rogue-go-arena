# Developer Tools

Utilities in this directory are not packaged into the game runtime.

Run the card balance evaluator from the repository root:

```powershell
python tools/card_balance_eval.py --help
```

## Card art medallions

`static/assets/icons/cards-medal/` holds the round card art shown in the game.
It is generated from the source art in `static/assets/icons/cards-tech/`
(needs Pillow), with a few per-card crop tweaks, plus three cards drawn from
scratch. Run from the repository root:

```powershell
python tools/card_art/normalize_art.py static/assets/icons/cards-tech static/assets/icons/cards-medal card-art-sheet.png nerf=0.95 joseki_ocd=0.92 capture_foul=0.9 seal=0.9 sansan_trap=0.88 time_press=0.66 lowline=0.92 defense_first=0.86
python tools/card_art/draw_streak_art.py static/assets/icons/cards-medal
```

Check `card-art-sheet.png` by eye, then bump `CARD_ART_VERSION` in
`static/js/card_catalog.js`.
