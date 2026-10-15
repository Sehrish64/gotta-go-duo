# Contributing to gotta-go-duo

The easiest way to help is to add content. No Python needed!

- **New character:** add an entry to `data/characters.json` (name, emoji, desc, special move).
- **New hurdle:** add an entry to `data/hurdles.json`. `rule` can be `any` (needs one of `good_moves`), `both_same`, or `different`.
- **New map:** add it to `data/maps.json` and list which hurdles can appear.
- **New sound:** add a 48 kHz, 16-bit, mono `.wav` to `assets/sounds/` (only use sounds you made or that are CC0).

Rules of the game: keep it silly and friendly, original characters only (no copyrighted characters), and keep jokes kind.

Before opening a PR, run `python -m py_compile bot.py cogs/*.py` and check your JSON is valid.
