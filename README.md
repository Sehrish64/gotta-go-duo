<p align="center"><img src="assets/banner.svg" alt="Gotta Go Duo banner" width="100%"></p>

<!-- Add your demo GIF here once recorded (see docs/DEMO_PLAN.md):
<p align="center"><img src="assets/demo.gif" alt="Gameplay demo" width="700"></p>
-->

# 🚽 gotta-go-duo

A silly **2-player panic game for Discord**. You and a friend share one panic meter and must reach the bathroom together before it hits 100%. Be a good teammate... or betray them for a Golden TP. 😈

> Inspired by the genre of bathroom-panic co-op games. All characters, places, and enemies here are original.

## Commands
- `/gotago friend:@someone [map] [discussion]`: start a game
- `/gotago_rules`: quick rules (only you see it)
- `/gotago_leaderboard [board]`: best duos, most wins, most loyal (helps), biggest traitors 😈
- `/gotago_stats [user]`: games, win rate, helps, betrayals and favourite partner
- `/gotago_stop`: stop the game in this channel (players or moderators)

## Play
1. `/gotago friend:@someone` (optionally pick a map)
2. Your friend taps **Let's go!**
3. Both pick a character
4. Every turn a hurdle appears. First comes **discussion time** (default 30s, you choose 0/20/30/45 in the command) where you plan, bluff and argue. Then the move buttons unlock and both players **secretly lock in a move**, and the bot reveals them together.

| Move | Steps | Panic | Notes |
|---|---|---|---|
| 🏃 Sprint | +2 | +14 | Fast but risky |
| 🦶 Tiptoe | +1 | +6 | Steady |
| 😬 Hold it | 0 | -10 | Cool down |
| 🤝 Help | +1 | -6 | Also cancels your buddy's dizziness |
| 😈 Betray | +2 | +8 | You get a Golden TP 🧻, buddy is dizzy next turn |
| ⭐ Special | varies | varies | Once per game, depends on character |

- Each hurdle is cleared by certain moves (the hurdle text tells you which). Clear it and you advance; fail and panic jumps.
- Both players picking the same safe move gives a small **sync bonus**.
- Golden TP auto-activates at 80% panic and drops the meter.
- Win by reaching the 🚽 (10 steps). Lose if panic hits 100%.
- You also get a **friendship score** at the end based on helps vs betrayals.

## 🎙️ Voice features
1. **Voice reminder:** the game tells you to join the same voice channel, and shows whether you are connected.
2. **Discussion / bluff phase:** each turn starts with a timer where the move buttons are locked, so you can talk it out (or lie to each other). Pick the length with the `discussion` option of `/gotago`.
3. **Sound effects:** if both players are in the same voice channel, the bot joins and plays honks, alarms, flushes, a sad trombone, and win/lose jingles. If you are not in voice, the game still works silently.

Sound effects need:
- `discord.py[voice]` (installed by `requirements.txt`, includes PyNaCl)
- On Linux, the Opus library: `sudo apt install libopus0`
- The bot role needs **Connect** and **Speak** permission in the voice channel
- No ffmpeg is needed. The sounds are plain `.wav` files that the bot plays directly.

All sounds are generated from scratch by `tools/make_sounds.py`, so they are copyright-free. Run it to regenerate or tweak them, or drop in your own **48 kHz, 16-bit, mono** `.wav` files with the same names in `assets/sounds/`.

Note: Discord allows one voice connection per server for a bot, so sound effects play for one game per server at a time.

## 📊 Leaderboard and stats
Every finished game (win or lose) is saved to a small **SQLite** file (`data/gotta_go.db`). It uses Python's built-in `sqlite3`, so it is free and needs no setup. Rankings are **per server**.
- 🏆 Best duos (wins, then average friendship score)
- 🥇 Most wins, 🤝 most loyal, 😈 biggest traitors
- Abandoned or stopped games are not counted.
- Only Discord user IDs and game stats are stored, nothing else. Change the file location with `DB_PATH` in `.env`.
- Back up or reset by copying or deleting the `.db` file.

## Run it
1. Create an app at <https://discord.com/developers/applications>, add a **Bot**, copy the token.
2. Invite it with the scopes `bot` and `applications.commands`, plus the permissions **Send Messages**, **Embed Links**, **Connect** and **Speak**. No special intents are needed.
3. ```bash
   python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env    # paste your token (and optionally DEV_GUILD_ID)
   python bot.py
   ```

## Add your own content (no code needed)
Everything lives in `data/`. Open a PR with new entries!
- `characters.json`: add a character with a special move
- `hurdles.json`: add a hurdle (`rule`: `any`, `both_same`, or `different`)
- `maps.json`: add a map and list which hurdles appear

Game balance knobs are at the top of `cogs/game.py`.

## Free hosting ideas
Any always-on free tier that can run Python works (Railway/Render/Fly free credits, an old laptop, a Raspberry Pi). Game state is in memory, so there is no database to pay for.

## Known limitations
- Running games live in memory, so restarting the bot ends them (saved leaderboard results stay).
- One game per channel, and sound effects for one game per server at a time.
- If both players skip 2 turns in a row, the game ends automatically.

## Making the repo shine on GitHub
- Record a demo GIF with `docs/DEMO_PLAN.md` and uncomment it at the top of this README.
- Add repo topics: `discord-bot`, `discord-py`, `python`, `game`, `multiplayer`, `fun`.
- Add a "Add to Discord" invite link once your bot is hosted.

## Roadmap ideas
- Funny fail GIFs and shareable result cards
- More sound effects (per character voices)
- Daily challenge map
- Unlockable outfits for the characters
- Weekly leaderboard reset and seasons
- More characters, hurdles, and languages

## License
MIT, see `LICENSE`.
