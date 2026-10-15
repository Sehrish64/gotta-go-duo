# gotta-go-duo: A se Z summary

## Idea kahan se aaya
- Aap ne "We Gotta Go" naam ke poop game ke baare mein poocha. Search mein mila ke yeh FuzzyBot ka haunted-mansion bathroom co-op game hai (Steam par). Ek purana "Gotta Go!" (Dire Nerd Studios) bhi hai.
- Aap ko Discord ke liye ek **naya, free, max 2 players, hansi mazaq wala** game repo chahiye tha, jo younger users search karein aur famous ho sake.
- Aap ne repo ka naam **gotta-go-duo** chuna, aur characters naye lekin us game ke jaise feel wale.

## Game kaise chalta hai
- `/gotago friend:@dost [map] [discussion]` se shuru hota hai. Dost "Let's go!" dabata hai, dono character chunte hain.
- Dono ka ek **shared panic meter** hai. Bathroom 🚽 tak 10 steps pohanchna hai, meter 100% hone se pehle.
- Har turn: hurdle aata hai, **discussion time** (talk/bluff), phir dono **secretly move lock** karte hain, bot dono moves ek saath reveal karta hai.
- Moves: Sprint, Tiptoe, Hold it, Help, Betray, Special (ek baar per game).
- Betray: partner dizzy ho jata hai aur aap ko Golden TP 🧻 milta hai (meter 80% par khud use hota hai).
- Aakhir mein friendship score (helps vs betrayals).

## Naye characters (original)
- 🧸 Pappu Panic (Tiptoe Ninja)
- 🦆 Captain Quack (Waddle Dash, HONK ka risk)
- 🧙 Wizard Wobbly (Cast Clench)
- 🥭 Mango Mike (Juice Slide)

## Maps aur hurdles
- Maps: 🏚️ Chacha's Haunted Haveli, 🎪 Spooky Shaadi Hall, 🎡 Moonlight Mela
- Hurdles: Stuck Door, Chatty Chachi Ghost, Slipper Bat, Biryani Blob, Mirror Twin, Dancing Uncles, Endless Buffet Line, Stuck Ferris Wheel
- Sab kuch `data/*.json` mein hai, bina code ke naye content add ho sakta hai.

## Voice features (aap ne teeno chune)
1. Voice reminder: embed mein dikhta hai ke aap voice mein hain ya nahi.
2. Discussion/bluff phase: har turn pehle talk time, buttons locked (Off/20/30/45 sec).
3. Sound effects: bot voice channel mein aa kar honk, alarm, flush, sad trombone, win/lose bajata hai. Sounds code se bane hain (`tools/make_sounds.py`), copyright-free. ffmpeg nahi chahiye, `discord.py[voice]` chahiye. Linux par `libopus0`. Bot ko Connect aur Speak permission.

## Baad mein add hua
- AFK bug fix: dono 2 turn skip karein to game khatam.
- `/gotago_stop`, `/gotago_rules`
- LICENSE (MIT), CONTRIBUTING.md
- SQLite leaderboard: `/gotago_leaderboard` (best duos, most wins, most loyal, biggest traitors) aur `/gotago_stats`
- README banner (`assets/banner.svg`) aur demo GIF plan (`docs/DEMO_PLAN.md`)

## Free hai ya nahi
- Haan, sab free hai: Discord bot token, discord.py, PyNaCl, python-dotenv, sqlite3, sounds. Koi paid API nahi.
- Sirf hosting ka masla: apna laptop pe `python bot.py`, ya free cloud tiers (shartein badalti rehti hain, khud check karein).

## Setup (short)
1. Discord Developer Portal par bot banayein, token copy karein.
2. Invite: scopes `bot` + `applications.commands`, permissions Send Messages, Embed Links, Connect, Speak.
3. `pip install -r requirements.txt`, `.env.example` ko `.env` banayein, token daalein, `python bot.py`.
4. Testing ke liye `.env` mein `DEV_GUILD_ID` daalein (commands turant dikhte hain).

## Abhi tak kya test hua aur kya nahi
- Hua: code compile, game engine ki simulation (random play ~62% jeet, careful ~85%), discussion timer, AFK end, leaderboard database (fake objects ke saath).
- **Nahi hua:** asli Discord par live test (buttons, voice connect, sounds). Banner ko image ki tarah dekha nahi gaya.
- Ye aap ko dost ke saath test karna hai.

## Aap ke agle kaam
1. Live test karein aur bug batayein.
2. Demo GIF record karein (`docs/DEMO_PLAN.md`).
3. GitHub topics lagayein: discord-bot, discord-py, python, game, multiplayer.
4. Bot host karein aur README mein "Add to Discord" link daalein.

## Folder structure
```
gotta-go-duo/
├── bot.py
├── cogs/ (game.py, sfx.py, db.py, leaderboard.py)
├── data/ (characters.json, hurdles.json, maps.json)
├── assets/ (banner.svg, sounds/*.wav)
├── tools/make_sounds.py
├── docs/ (DEMO_PLAN.md, PROJECT_SUMMARY.md)
├── README.md, CONTRIBUTING.md, LICENSE
└── requirements.txt, .env.example, .gitignore
```
