"""gotta-go-duo: a 2-player panic game for Discord."""
import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()


class GottaGoBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=discord.Intents.default(),
        )

    async def setup_hook(self) -> None:
        await self.load_extension("cogs.game")
        await self.load_extension("cogs.leaderboard")
        guild_id = os.getenv("DEV_GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)  # instant, for testing
        else:
            await self.tree.sync()  # global, can take a while to appear

    async def on_ready(self) -> None:
        print(f"🚽 Logged in as {self.user} - ready to go!")


async def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Missing DISCORD_TOKEN. Copy .env.example to .env first.")
    async with GottaGoBot() as bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
