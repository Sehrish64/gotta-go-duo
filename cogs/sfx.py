"""Tiny voice sound-effect helper.

Needs PyNaCl (installed via discord.py[voice]). Does NOT need ffmpeg:
the wav files are decoded here and fed straight to discord.PCMAudio.
"""
from __future__ import annotations

import asyncio
import io
import sys
import wave
from array import array
from pathlib import Path

import discord

SOUNDS = Path(__file__).resolve().parent.parent / "assets" / "sounds"
VOLUME = 0.6

try:
    import nacl  # noqa: F401
    HAS_NACL = True
except ImportError:  # voice libs missing: the game still works, just silent
    HAS_NACL = False


class SoundBoard:
    def __init__(self) -> None:
        self.cache: dict[str, bytes] = {}
        self.enabled = HAS_NACL
        self._load()

    def _load(self) -> None:
        for path in SOUNDS.glob("*.wav"):
            with wave.open(str(path), "rb") as w:
                if w.getframerate() != 48000 or w.getnchannels() != 1 or w.getsampwidth() != 2:
                    continue  # only 48kHz mono 16-bit is supported
                mono = array("h")
                mono.frombytes(w.readframes(w.getnframes()))
            if sys.byteorder == "big":
                mono.byteswap()
            stereo = array("h", [0]) * (len(mono) * 2)
            stereo[0::2] = mono
            stereo[1::2] = mono
            if sys.byteorder == "big":
                stereo.byteswap()
            self.cache[path.stem] = stereo.tobytes()

    async def play(self, channel: discord.VoiceChannel, name: str) -> None:
        if not self.enabled or name not in self.cache:
            return
        guild = channel.guild
        perms = channel.permissions_for(guild.me)
        if not (perms.connect and perms.speak):
            return
        vc = guild.voice_client
        if vc is None:
            vc = await channel.connect(timeout=10)
        elif vc.channel.id != channel.id:
            await vc.move_to(channel)
        if vc.is_playing():
            vc.stop()
        source = discord.PCMVolumeTransformer(discord.PCMAudio(io.BytesIO(self.cache[name])), volume=VOLUME)
        vc.play(source)

    async def leave(self, guild: discord.Guild) -> None:
        vc = guild.voice_client
        if vc is None:
            return
        for _ in range(40):  # let the last sound finish (max ~8s)
            if not vc.is_playing():
                break
            await asyncio.sleep(0.2)
        await vc.disconnect()
