"""Leaderboard and stats commands."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from .db import Store

MEDALS = ["🥇", "🥈", "🥉"]
BOARDS = {
    "duos": ("🏆 Best duos", None),
    "wins": ("🥇 Most wins", "wins"),
    "helps": ("🤝 Most loyal (helps)", "helps"),
    "betrays": ("😈 Biggest traitors", "betrays"),
}


def rank(i: int) -> str:
    return MEDALS[i] if i < 3 else f"**{i + 1}.**"


class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.store = Store()

    @app_commands.command(name="gotago_leaderboard", description="See the best duos and players in this server")
    @app_commands.guild_only()
    @app_commands.describe(board="Which ranking to show")
    @app_commands.choices(board=[app_commands.Choice(name=v[0], value=k) for k, v in BOARDS.items()])
    async def leaderboard(self, interaction: discord.Interaction, board: app_commands.Choice[str] | None = None):
        kind = board.value if board else "duos"
        title, column = BOARDS[kind]
        gid = interaction.guild_id

        if kind == "duos":
            rows = await self.store.top_duos(gid)
            lines = [
                f"{rank(i)} <@{r['user_a']}> + <@{r['user_b']}>: **{r['wins']}** wins / {r['games']} games, "
                f"avg friendship **{r['avg_score']:.0f}**" + (f", fastest win {r['fastest_win']} turns" if r["fastest_win"] else "")
                for i, r in enumerate(rows)
            ]
        else:
            rows = await self.store.top_players(gid, column)
            lines = [f"{rank(i)} <@{r['user_id']}>: **{r[column]}** ({r['games']} games)" for i, r in enumerate(rows)]

        e = discord.Embed(title=title, colour=discord.Colour.gold(),
                          description="\n".join(lines) if lines else "No games saved yet. Play one with /gotago! 🚽")
        e.set_footer(text="Only finished games (win or lose) count.")
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="gotago_stats", description="Your Gotta Go Duo stats")
    @app_commands.guild_only()
    @app_commands.describe(user="Whose stats to show (default: you)")
    async def stats(self, interaction: discord.Interaction, user: discord.Member | None = None):
        target = user or interaction.user
        data = await self.store.player(interaction.guild_id, target.id)
        if data is None:
            return await interaction.response.send_message(f"{target.display_name} hasn't finished a game here yet.", ephemeral=True)

        e = discord.Embed(title=f"🚽 {target.display_name}'s stats", colour=discord.Colour.blurple())
        e.add_field(name="Games", value=str(data["games"]))
        e.add_field(name="Wins", value=str(data["wins"]))
        e.add_field(name="Win rate", value=f"{100 * data['wins'] / data['games']:.0f}%")
        e.add_field(name="🤝 Helps", value=str(data["helps"]))
        e.add_field(name="😈 Betrayals", value=str(data["betrays"]))
        p = data["partner"]
        if p:
            buddy = p["user_b"] if p["user_a"] == target.id else p["user_a"]
            e.add_field(name="Favourite partner", value=f"<@{buddy}> ({p['games']} games, avg friendship {p['avg_score']:.0f})", inline=False)
        await interaction.response.send_message(embed=e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LeaderboardCog(bot))
