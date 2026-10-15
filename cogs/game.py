"""Core game logic and Discord UI for /gotago."""
from __future__ import annotations

import asyncio
import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from .db import Store
from .sfx import SoundBoard

DATA = Path(__file__).resolve().parent.parent / "data"


def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


CHARACTERS = _load("characters.json")
HURDLES = _load("hurdles.json")
MAPS = _load("maps.json")

# ---- Tuning knobs: change these to rebalance the game ----
START_PANIC = 20
PASSIVE_PANIC = 5      # panic that rises every turn no matter what
MAX_PANIC = 100
TP_TRIGGER = 80        # Golden TP auto-activates at this panic level
TP_RELIEF = 20
SYNC_BONUS = 3         # panic removed when both pick the same safe move
TURN_SECONDS = 45       # time to lock in a move (after discussion ends)
DEFAULT_DISCUSSION = 30  # seconds of talking time before moves unlock (0 = off)
IDLE_LIMIT = 2          # end the game if both players skip this many turns in a row
SFX_PRIORITY = ["honk", "betray", "flush", "fail", "success"]

MOVES = {
    "sprint":  {"label": "Sprint",  "emoji": "🏃", "step": 2, "panic": 14},
    "tiptoe":  {"label": "Tiptoe",  "emoji": "🦶", "step": 1, "panic": 6},
    "hold":    {"label": "Hold it", "emoji": "😬", "step": 0, "panic": -10},
    "help":    {"label": "Help",    "emoji": "🤝", "step": 1, "panic": -6},
    "betray":  {"label": "Betray",  "emoji": "😈", "step": 2, "panic": 8},
    "special": {"label": "Special", "emoji": "⭐", "step": 0, "panic": 0},
}

WIN_LINES = [
    "🎉 FLUSH! You both made it to the 🚽. Absolute legends.",
    "🎉 The door slams shut. Peace at last. You both win!",
]
LOSE_LINES = [
    "💥 ACCIDENT! The panic meter exploded. Nobody will speak of this.",
    "💥 Too late... 💩 You both lose. Tell no one.",
]


# ------------------------------------------------------------------ models
@dataclass
class Player:
    user: discord.abc.User
    char_id: str | None = None
    move: str | None = None
    special_used: bool = False
    stunned: bool = False
    golden_tp: int = 0
    helps: int = 0
    betrays: int = 0

    @property
    def char(self) -> dict:
        return CHARACTERS[self.char_id]

    @property
    def name(self) -> str:
        return self.user.display_name


@dataclass
class Game:
    channel_id: int
    players: list[Player]
    map_id: str
    meter: int = START_PANIC
    progress: int = 0
    turn: int = 0
    hurdle_id: str | None = None
    message: discord.Message | None = None
    view: discord.ui.View | None = None
    last_lines: list[str] = field(default_factory=list)
    finished: bool = False
    guild_id: int = 0
    discussion: int = 0
    discussing: bool = False
    phase_ends: int = 0
    sfx: list[str] = field(default_factory=list)
    idle_turns: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def player_for(self, user_id: int) -> Player | None:
        return next((p for p in self.players if p.user.id == user_id), None)

    def other(self, player: Player) -> Player:
        return self.players[1] if player is self.players[0] else self.players[0]


# --------------------------------------------------------------- voice helpers
def shared_voice_channel(game: Game):
    """The voice channel both players are in right now (or None)."""
    chans = []
    for p in game.players:
        vs = getattr(p.user, "voice", None)
        chans.append(vs.channel if vs and vs.channel else None)
    if chans[0] and chans[1] and chans[0].id == chans[1].id:
        return chans[0]
    return None


def voice_line(game: Game) -> str:
    ch = shared_voice_channel(game)
    if ch:
        sound = " | 🔊 Sound effects ON" if isinstance(ch, discord.VoiceChannel) else ""
        return f"🎙️ Voice chat ON in **{ch.name}**{sound}"
    return "🎙️ Join the same voice channel and talk to your buddy! (Voice channel join karo, maza double hoga 😎)"


# --------------------------------------------------------------- rendering
def meter_bar(meter: int) -> str:
    blocks = max(0, min(10, round(meter / 10)))
    colour = "🟩" if meter < 40 else "🟨" if meter < 70 else "🟥"
    return colour * blocks + "⬜" * (10 - blocks) + f" **{meter}%**"


def track(progress: int, length: int) -> str:
    pos = max(0, min(length, progress))
    return "▫️" * pos + "🧍🧍" + "▫️" * (length - pos) + "🚽"


def track_running(progress: int, length: int, duo: str, frame: int) -> str:
    """Progress bar with the duo visibly mid-run (dash alternates each frame)."""
    pos = max(0, min(length, progress))
    dash = "💨" if frame % 2 == 0 else "💨💨"
    return "▫️" * pos + f"{duo}{dash}" + "▫️" * (length - pos) + "🚽"


def turn_embed(game: Game, lines: list[str] | None = None) -> discord.Embed:
    m, h = MAPS[game.map_id], HURDLES[game.hurdle_id]
    e = discord.Embed(
        title=f"{m['emoji']} {m['name']} - Turn {game.turn}",
        colour=discord.Colour.orange(),
    )
    if lines:
        e.add_field(name="📣 Last turn", value="\n".join(lines)[:1024], inline=False)
    e.add_field(name=f"{h['emoji']} Hurdle: {h['name']}", value=h["text"], inline=False)
    e.add_field(name="😰 Panic meter", value=meter_bar(game.meter), inline=False)
    e.add_field(name="🗺️ Progress", value=track(game.progress, m["length"]), inline=False)
    status = "\n".join(
        f"{p.char['emoji']} **{p.name}** - {'🔒 locked in' if p.move else '⏳ thinking...'}"
        for p in game.players
    )
    e.add_field(name="Duo", value=status, inline=False)
    if game.discussing:
        e.add_field(
            name="🗣️ Discussion time!",
            value=f"Plan, bluff, argue... in voice or chat. Moves unlock <t:{game.phase_ends}:R>.",
            inline=False,
        )
        e.set_footer(text="Buttons unlock when discussion ends.")
    else:
        e.set_footer(text=f"Moves are secret until both lock in. {TURN_SECONDS}s per turn.")
    e.add_field(name="Voice", value=voice_line(game), inline=False)
    return e


def friendship(game: Game) -> tuple[int, str]:
    helps = sum(p.helps for p in game.players)
    betrays = sum(p.betrays for p in game.players)
    score = max(0, min(100, 50 + 10 * helps - 15 * betrays))
    title = (
        "Bathroom besties 💛" if score >= 80 else
        "Solid duo 🤝" if score >= 50 else
        "Frenemies 😬" if score >= 25 else
        "Total backstabbers 😈"
    )
    return score, title


def end_embed(game: Game, lines: list[str], won: bool) -> discord.Embed:
    score, title = friendship(game)
    e = discord.Embed(
        title="🚽 YOU MADE IT!" if won else "💩 GAME OVER",
        description=random.choice(WIN_LINES if won else LOSE_LINES),
        colour=discord.Colour.green() if won else discord.Colour.red(),
    )
    if lines:
        e.add_field(name="📣 Final turn", value="\n".join(lines)[:1024], inline=False)
    e.add_field(name="Turns", value=str(game.turn), inline=True)
    e.add_field(name="Friendship score", value=f"{score}/100 - {title}", inline=True)
    e.add_field(
        name="Stats",
        value="\n".join(f"{p.char['emoji']} {p.name}: {p.helps} helps, {p.betrays} betrayals" for p in game.players),
        inline=False,
    )
    e.set_footer(text="Result saved! Run /gotago to go again or /gotago_leaderboard for rankings.")
    return e


# ------------------------------------------------------------ game engine
def _effect(game: Game, p: Player, lines: list[str]) -> dict:
    """Work out what one player's locked-in move does."""
    if p.move == "special":
        sp = p.char["special"]
        p.special_used = True
        eff = {
            "label": f"⭐ {sp['name']}",
            "step": sp.get("step", 0),
            "panic": sp.get("panic", 0),
            "clear": sp.get("clear_hurdle", False),
            "stun_partner": sp.get("stun_partner", False),
        }
        risk = sp.get("risk")
        if risk and random.random() < risk["chance"]:
            eff["panic"] += risk["panic"]
            lines.append(f"🦆 {risk['text']}")
            game.sfx.append("honk")
        return eff

    mv = MOVES[p.move]
    eff = {"label": f"{mv['emoji']} {mv['label']}", "step": mv["step"], "panic": mv["panic"],
           "clear": False, "stun_partner": False}
    if p.move == "help":
        p.helps += 1
    if p.move == "betray":
        p.betrays += 1
        p.golden_tp += 1
        eff["stun_partner"] = True
        game.sfx.append("betray")
    return eff


def resolve_turn(game: Game) -> list[str]:
    a, b = game.players
    hurdle = HURDLES[game.hurdle_id]
    length = MAPS[game.map_id]["length"]
    lines: list[str] = []
    game.sfx = []
    game.idle_turns = game.idle_turns + 1 if all(p.move is None for p in game.players) else 0

    for p in game.players:
        if p.move is None:
            p.move = "hold"
            lines.append(f"⏰ **{p.name}** froze up and just held it.")

    # stuns from last turn (a partner's Help cancels yours this turn)
    was_stunned = {id(p): p.stunned and game.other(p).move != "help" for p in game.players}
    for p in game.players:
        p.stunned = False

    effects = {id(p): _effect(game, p, lines) for p in game.players}
    reveal = " | ".join(f"{p.char['emoji']} **{p.name}** → {effects[id(p)]['label']}" for p in game.players)
    lines.insert(0, reveal)

    step_total, panic_total = 0, PASSIVE_PANIC
    for p in game.players:
        e = effects[id(p)]
        if was_stunned[id(p)]:
            e["step"] = 0
            lines.append(f"😵 **{p.name}** was dizzy and couldn't move forward.")
        step_total += e["step"]
        panic_total += e["panic"]
        if e["stun_partner"]:
            game.other(p).stunned = True
            if p.move == "betray":
                lines.append(f"😈 **{p.name}** BETRAYED **{game.other(p).name}**! Grabbed a Golden TP 🧻 and shoved them over.")
            else:
                lines.append(f"🥭 **{p.name}** left a slippery mess. **{game.other(p).name}** will be dizzy next turn.")

    a_move, b_move = a.move, b.move
    if hurdle["rule"] == "any":
        cleared = a_move in hurdle["good_moves"] or b_move in hurdle["good_moves"]
    elif hurdle["rule"] == "both_same":
        cleared = a_move == b_move
    else:  # "different"
        cleared = a_move != b_move
    cleared = cleared or any(e["clear"] for e in effects.values())

    if cleared:
        game.progress += step_total
        lines.append(f"✅ {hurdle['win_text']} (+{step_total} steps)")
        game.sfx.append("success")
    else:
        panic_total += hurdle["fail_panic"]
        lines.append(f"❌ {hurdle['fail_text']} (+{hurdle['fail_panic']} panic)")
        game.sfx.append("fail")

    if a_move == b_move and a_move in ("sprint", "tiptoe", "hold", "help"):
        panic_total -= SYNC_BONUS
        lines.append(f"🎯 Perfectly in sync! (-{SYNC_BONUS} panic)")

    game.meter = max(0, game.meter + panic_total)
    game.progress = min(length, game.progress)

    if game.meter >= TP_TRIGGER:
        for p in game.players:
            if p.golden_tp > 0:
                p.golden_tp -= 1
                game.meter = max(0, game.meter - TP_RELIEF)
                lines.append(f"🧻 **{p.name}** used a Golden TP! (-{TP_RELIEF} panic)")
                game.sfx.append("flush")
                break

    for p in game.players:
        p.move = None
    return lines


# ----------------------------------------------------------------- views
class InviteView(discord.ui.View):
    def __init__(self, cog: "GameCog", host: discord.abc.User, guest: discord.abc.User, map_id: str, discussion: int):
        super().__init__(timeout=60)
        self.cog, self.host, self.guest, self.map_id = cog, host, guest, map_id
        self.discussion = discussion
        self.message: discord.Message | None = None

    @discord.ui.button(label="Let's go!", emoji="🚽", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.guest.id:
            return await interaction.response.send_message("Only the invited friend can accept 😅", ephemeral=True)
        game = Game(
            channel_id=interaction.channel_id,
            players=[Player(self.host), Player(self.guest)],
            map_id=self.map_id,
            guild_id=interaction.guild_id or 0,
            discussion=self.discussion,
        )
        self.cog.games[interaction.channel_id] = game
        game.message = interaction.message
        view = CharacterView(self.cog, game)
        game.view = view
        self.stop()
        await interaction.response.edit_message(embed=view.embed(), view=view)

    @discord.ui.button(label="No thanks", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id not in (self.guest.id, self.host.id):
            return await interaction.response.send_message("Not your invite!", ephemeral=True)
        self.cog.pending.discard(interaction.channel_id)
        self.stop()
        await interaction.response.edit_message(content="Invite cancelled. Maybe next time. 🚪", embed=None, view=None)

    async def on_timeout(self) -> None:
        self.cog.pending.discard(self.message.channel.id)
        await self.message.edit(content="Nobody answered in time. The bathroom is lonely. 🚪", embed=None, view=None)


class CharacterSelect(discord.ui.Select):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Pick your character...",
            options=[
                discord.SelectOption(label=c["name"], value=cid, emoji=c["emoji"],
                                     description=f"{c['desc']} | ⭐ {c['special']['name']}"[:100])
                for cid, c in CHARACTERS.items()
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        view: CharacterView = self.view
        player = view.game.player_for(interaction.user.id)
        if not player:
            return await interaction.response.send_message("This isn't your game!", ephemeral=True)
        player.char_id = self.values[0]
        await interaction.response.send_message(
            f"You picked {player.char['emoji']} **{player.char['name']}**. Special: ⭐ {player.char['special']['name']} "
            f"({player.char['special']['desc']}). Once per game!",
            ephemeral=True,
        )
        if all(p.char_id for p in view.game.players):
            view.stop()
            await view.cog.begin_turn(view.game)
        else:
            await view.game.message.edit(embed=view.embed(), view=view)


class CharacterView(discord.ui.View):
    def __init__(self, cog: "GameCog", game: Game):
        super().__init__(timeout=90)
        self.cog, self.game = cog, game
        self.add_item(CharacterSelect())

    def embed(self) -> discord.Embed:
        m = MAPS[self.game.map_id]
        e = discord.Embed(
            title=f"{m['emoji']} {m['name']}",
            description="Both players: pick your character from the menu below!",
            colour=discord.Colour.blurple(),
        )
        e.add_field(
            name="Duo",
            value="\n".join(
                f"**{p.name}** - {p.char['emoji'] + ' ' + p.char['name'] if p.char_id else '⏳ choosing...'}"
                for p in self.game.players
            ),
        )
        e.add_field(name="Voice", value=voice_line(self.game), inline=False)
        return e

    async def on_timeout(self) -> None:
        if not self.game.finished:
            self.cog.remove(self.game)
            await self.game.message.edit(content="Character select timed out. 🚪", embed=None, view=None)


class MoveButton(discord.ui.Button):
    def __init__(self, key: str):
        mv = MOVES[key]
        style = (discord.ButtonStyle.danger if key == "betray"
                 else discord.ButtonStyle.primary if key == "special"
                 else discord.ButtonStyle.secondary)
        super().__init__(label=mv["label"], emoji=mv["emoji"], style=style)
        self.key = key

    async def callback(self, interaction: discord.Interaction):
        await self.view.handle(interaction, self.key)


class TurnView(discord.ui.View):
    def __init__(self, cog: "GameCog", game: Game, token: int):
        super().__init__(timeout=game.discussion + TURN_SECONDS)
        self.cog, self.game, self.token = cog, game, token
        for key in MOVES:
            btn = MoveButton(key)
            btn.disabled = game.discussing
            self.add_item(btn)

    def unlock(self) -> None:
        for child in self.children:
            child.disabled = False

    async def handle(self, interaction: discord.Interaction, key: str):
        game = self.game
        player = game.player_for(interaction.user.id)
        if not player:
            return await interaction.response.send_message("This isn't your game! Start one with /gotago 🚽", ephemeral=True)
        if game.discussing:
            return await interaction.response.send_message("Discussion time! Talk first, moves unlock soon 🗣️", ephemeral=True)
        if player.move:
            return await interaction.response.send_message("You already locked in! Wait for your buddy 😅", ephemeral=True)
        if key == "special" and player.special_used:
            return await interaction.response.send_message("You already used your special this game!", ephemeral=True)

        player.move = key
        label = f"⭐ {player.char['special']['name']}" if key == "special" else MOVES[key]["label"]
        await interaction.response.send_message(f"🔒 Locked in **{label}**. Shh, don't tell your buddy!", ephemeral=True)

        if all(p.move for p in game.players):
            await self.cog.advance(game, self.token)
        else:
            await game.message.edit(embed=turn_embed(game, game.last_lines), view=self)

    async def on_timeout(self) -> None:
        await self.cog.advance(self.game, self.token)


# ------------------------------------------------------------------- cog
class GameCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.games: dict[int, Game] = {}
        self.pending: set[int] = set()
        self.board = SoundBoard()
        self.store = Store()
        self._tasks: set[asyncio.Task] = set()

    # -- background helpers
    def spawn(self, coro) -> None:
        async def runner():
            try:
                await coro
            except Exception as exc:  # never let a side task crash the game
                print(f"[gotta-go-duo] background task error: {exc!r}")
        task = asyncio.create_task(runner())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def play_sfx(self, game: Game, name: str, leave: bool = False) -> None:
        try:
            ch = shared_voice_channel(game)
            if isinstance(ch, discord.VoiceChannel):
                await self.board.play(ch, name)
        finally:
            if leave:
                await self.hangup(game)

    async def hangup(self, game: Game) -> None:
        if any(g.guild_id == game.guild_id for g in self.games.values()):
            return  # another game in this server still needs the voice link
        guild = self.bot.get_guild(game.guild_id)
        if guild:
            await self.board.leave(guild)

    async def save_result(self, game: Game, won: bool) -> None:
        if not game.guild_id:
            return
        score, _ = friendship(game)
        await self.store.record_game(
            game.guild_id, [(p.user.id, p.helps, p.betrays) for p in game.players], won, game.turn, score
        )

    def remove(self, game: Game, leave: bool = True) -> None:
        game.finished = True
        self.games.pop(game.channel_id, None)
        self.pending.discard(game.channel_id)
        if leave:
            self.spawn(self.hangup(game))

    # -- turn flow
    async def begin_turn(self, game: Game, lines: list[str] | None = None) -> None:
        game.turn += 1
        game.hurdle_id = random.choice(MAPS[game.map_id]["hurdles"])
        game.last_lines = lines or []
        game.discussing = game.discussion > 0
        game.phase_ends = int(time.time()) + game.discussion
        view = TurnView(self, game, game.turn)
        game.view = view
        await game.message.edit(embed=turn_embed(game, lines), view=view)
        if game.discussing:
            self.spawn(self.open_moves(game, game.turn, view))
        if game.turn == 1:
            self.spawn(self.play_sfx(game, "alarm"))

    async def open_moves(self, game: Game, token: int, view: TurnView) -> None:
        await asyncio.sleep(game.discussion)
        async with game.lock:
            if game.finished or game.turn != token:
                return
            game.discussing = False
            view.unlock()
            await game.message.edit(embed=turn_embed(game, game.last_lines), view=view)

    async def animate_run(self, game: Game, old: int, new: int, lines: list[str]) -> None:
        """Frame-by-frame running animation: the duo visibly rushes forward square by square."""
        if new <= old or game.finished or not game.message:
            return
        length = MAPS[game.map_id]["length"]
        duo = f"{game.players[0].char['emoji']}{game.players[1].char['emoji']}"
        total = new - old
        frames = min(total, 4)  # cap edits to respect Discord rate limits
        positions = [old + round(total * i / frames) for i in range(1, frames + 1)]
        for idx, pos in enumerate(positions):
            if game.finished:
                return
            e = discord.Embed(
                title=f"🏃 BHAGO! Turn {game.turn}",
                colour=discord.Colour.orange(),
            )
            if lines:
                e.add_field(name="📣 Last turn", value="\n".join(lines)[:1024], inline=False)
            e.add_field(name="😰 Panic meter", value=meter_bar(game.meter), inline=False)
            e.add_field(name="🗺️ Progress", value=track_running(pos, length, duo, idx), inline=False)
            e.set_footer(text="Bhago bhago, bathroom qareeb hai! 🏃💨🚽")
            try:
                await game.message.edit(embed=e, view=None)
            except Exception:
                return
            await asyncio.sleep(1.0)

    async def advance(self, game: Game, token: int) -> None:
        async with game.lock:
            if game.finished or token != game.turn:
                return  # already handled (double click or timeout race)
            if game.view:
                game.view.stop()
            old_progress = game.progress
            lines = resolve_turn(game)
            length = MAPS[game.map_id]["length"]
            if game.idle_turns >= IDLE_LIMIT:
                self.remove(game)
                e = discord.Embed(
                    title="😴 Game abandoned",
                    description="Nobody locked in a move for a while, so the bathroom door closed. Run /gotago to try again!",
                    colour=discord.Colour.dark_grey(),
                )
                await game.message.edit(embed=e, view=None)
            elif game.progress >= length or game.meter >= MAX_PANIC:
                won = game.progress >= length and game.meter < MAX_PANIC
                if won:
                    await self.animate_run(game, old_progress, game.progress, lines)
                self.remove(game, leave=False)
                self.spawn(self.save_result(game, won))
                self.spawn(self.play_sfx(game, "win" if won else "lose", leave=True))
                await game.message.edit(embed=end_embed(game, lines, won), view=None)
            else:
                sound = next((n for n in SFX_PRIORITY if n in game.sfx), None)
                if sound:
                    self.spawn(self.play_sfx(game, sound))
                await self.animate_run(game, old_progress, game.progress, lines)
                await self.begin_turn(game, lines)

    # -- slash command
    @app_commands.command(name="gotago", description="Race a friend to the bathroom! 🚽")
    @app_commands.guild_only()
    @app_commands.describe(
        friend="Your duo partner",
        map="Pick a spooky place (random if empty)",
        discussion="Talking time before moves unlock each turn (default 30s)",
    )
    @app_commands.choices(
        map=[app_commands.Choice(name="🎲 Random", value="random")]
        + [app_commands.Choice(name=f"{m['emoji']} {m['name']}", value=k) for k, m in MAPS.items()],
        discussion=[
            app_commands.Choice(name="Off (instant moves)", value=0),
            app_commands.Choice(name="20 seconds", value=20),
            app_commands.Choice(name="30 seconds", value=30),
            app_commands.Choice(name="45 seconds", value=45),
        ],
    )
    async def gotago(self, interaction: discord.Interaction, friend: discord.Member,
                     map: app_commands.Choice[str] | None = None,
                     discussion: app_commands.Choice[int] | None = None):
        if friend.bot or friend.id == interaction.user.id:
            return await interaction.response.send_message("Pick a real friend (not yourself or a bot)! 😄", ephemeral=True)
        cid = interaction.channel_id
        if cid in self.games or cid in self.pending:
            return await interaction.response.send_message("A game is already running in this channel!", ephemeral=True)

        map_id = random.choice(list(MAPS)) if map is None or map.value == "random" else map.value
        secs = DEFAULT_DISCUSSION if discussion is None else discussion.value
        self.pending.add(cid)
        view = InviteView(self, interaction.user, friend, map_id, secs)
        talk = f"🗣️ Discussion time: **{secs}s** per turn" if secs else "🗣️ Discussion time: off"
        embed = discord.Embed(
            title="🚽 Gotta Go Duo",
            description=(f"{friend.mention}, **{interaction.user.display_name}** needs a partner!\n\n"
                         f"Reach the bathroom together before the panic meter hits 100%.\n"
                         f"Place: {MAPS[map_id]['emoji']} **{MAPS[map_id]['name']}**\n{talk}\n\n"
                         f"🎙️ Tip: both of you join the same voice channel. The bot will join too and play funny sound effects! "
                         f"(Voice channel join karo, maza double hoga)"),
            colour=discord.Colour.gold(),
        )
        await interaction.response.send_message(content=friend.mention, embed=embed, view=view)
        view.message = await interaction.original_response()


    @app_commands.command(name="gotago_stop", description="Stop the game running in this channel")
    @app_commands.guild_only()
    async def gotago_stop(self, interaction: discord.Interaction):
        game = self.games.get(interaction.channel_id)
        if game is None:
            return await interaction.response.send_message("No game is running here.", ephemeral=True)
        allowed = game.player_for(interaction.user.id) is not None or interaction.permissions.manage_messages
        if not allowed:
            return await interaction.response.send_message("Only the players (or a moderator) can stop this game.", ephemeral=True)
        async with game.lock:
            if game.view:
                game.view.stop()
            self.remove(game)
            e = discord.Embed(title="🛑 Game stopped", description=f"Stopped by {interaction.user.display_name}.", colour=discord.Colour.dark_grey())
            await game.message.edit(embed=e, view=None)
        await interaction.response.send_message("Game stopped.", ephemeral=True)

    @app_commands.command(name="gotago_rules", description="How to play Gotta Go Duo")
    async def gotago_rules(self, interaction: discord.Interaction):
        e = discord.Embed(title="🚽 How to play", colour=discord.Colour.gold(),
                          description="Reach the bathroom together before the shared panic meter hits 100%.")
        e.add_field(name="Each turn", value="1. Discussion time (talk in voice or chat)\n2. Secretly lock in a move\n3. The bot reveals both moves at once", inline=False)
        e.add_field(
            name="Moves",
            value="\n".join(f"{m['emoji']} **{m['label']}**: {m['step']:+d} steps, {m['panic']:+d} panic" for m in MOVES.values() if m["label"] != "Special")
                  + "\n⭐ **Special**: once per game, depends on your character",
            inline=False,
        )
        e.add_field(name="Tips", value="Read the hurdle text, it tells you which moves clear it. Betraying is funny but costs friendship points. 😈", inline=False)
        await interaction.response.send_message(embed=e, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GameCog(bot))
