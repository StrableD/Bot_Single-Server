import asyncio
import os

import discord
import yt_dlp
from discord import FFmpegPCMAudio, app_commands
from discord.ext.commands import Cog

from lib.bot import My_Bot
from lib.helper.constants import BOTPATH

CACHE_DIR = os.path.join(BOTPATH, "data", "music_cache")
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)


class Music(Cog):
    """
    Das Modul, welches die Musikunterstützung zu dem Bot hinzufügt.
    """

    music_group = app_commands.Group(name="music", description="Music")
    playlist_group = app_commands.Group(
        name="playlist", description="Playlist", parent=music_group
    )

    def __init__(self, bot: My_Bot):
        self.bot = bot
        self.voice_channel = None
        self.is_playing = False
        self.music_queue = []

        self.YDL_OPTIONS = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(CACHE_DIR, "%(id)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
        }
        self.FFMPEG_OPTIONS = {"options": "-vn"}

    async def search_and_download(self, item):
        loop = asyncio.get_event_loop()

        def download():
            with yt_dlp.YoutubeDL(self.YDL_OPTIONS) as ydl:
                try:
                    info = ydl.extract_info(f"ytsearch:{item}", download=True)
                    if "entries" in info:
                        info = info["entries"][0]
                    filename = ydl.prepare_filename(info)
                    return {"source": filename, "title": info["title"]}
                except Exception as e:
                    print(e)
                    return False

        return await loop.run_in_executor(None, download)

    def play_next(self, guild: discord.Guild):
        if len(self.music_queue) > 0:
            self.is_playing = True
            m_url = self.music_queue.pop(0)["source"]
            if guild.voice_client:
                guild.voice_client.play(
                    FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS),
                    after=lambda e: self.play_next(guild),
                )
        else:
            self.is_playing = False

    async def _join(self, user: discord.Member, guild: discord.Guild) -> bool:
        if user.voice is None:
            return False
        voiceChannel = user.voice.channel
        if guild.voice_client is None:
            await voiceChannel.connect()
        elif (
            not guild.voice_client.is_connected()
            and guild.voice_client.channel != voiceChannel
        ):
            await voiceChannel.connect()
        return True

    @music_group.command(name="play", description="Spielt Musik von YouTube ab.")
    async def play_track(self, interaction: discord.Interaction, search: str):
        await interaction.response.defer(ephemeral=True)
        song = await self.search_and_download(search)
        if isinstance(song, bool):
            await interaction.followup.send(
                "Konnte das Lied nicht finden oder herunterladen.", ephemeral=True
            )
        else:
            self.music_queue.append(song)

            if not self.is_playing:
                joined = await self._join(interaction.user, interaction.guild)
                if not joined:
                    await interaction.followup.send(
                        "Du musst mit einem Sprachkanal verbunden sein.", ephemeral=True
                    )
                    return
                self.play_next(interaction.guild)
                await interaction.followup.send(f"Spielt jetzt: {song['title']}")
            else:
                await interaction.followup.send(
                    f"Zur Warteschlange hinzugefügt: {song['title']}"
                )

    @music_group.command(name="join", description="Tritt dem Sprachkanal bei.")
    async def join_channel(self, interaction: discord.Interaction):
        joined = await self._join(interaction.user, interaction.guild)
        if not joined:
            await interaction.response.send_message(
                "Du musst mit einem Sprachkanal verbunden sein.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Sprachkanal beigetreten.", ephemeral=True
            )

    @music_group.command(name="leave", description="Verlässt den Sprachkanal.")
    async def leave_channel(self, interaction: discord.Interaction):
        if (
            interaction.guild.voice_client
            and interaction.guild.voice_client.is_connected()
        ):
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message(
                "Sprachkanal verlassen.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Der Bot ist in keinem Sprachkanal.", ephemeral=True
            )

    @music_group.command(name="pause", description="Pausiert die aktuelle Musik.")
    async def pause_track(self, interaction: discord.Interaction):
        if (
            interaction.guild.voice_client
            and interaction.guild.voice_client.is_playing()
        ):
            interaction.guild.voice_client.pause()
            await interaction.response.send_message("Musik pausiert.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "Zurzeit wird keine Musik abgespielt.", ephemeral=True
            )

    @music_group.command(name="resume", description="Setzt die aktuelle Musik fort.")
    async def resume_track(self, interaction: discord.Interaction):
        if (
            interaction.guild.voice_client
            and interaction.guild.voice_client.is_paused()
        ):
            interaction.guild.voice_client.resume()
            await interaction.response.send_message(
                "Musik fortgesetzt.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Es wird noch Musik gespielt oder es gibt nichts fortzusetzen.",
                ephemeral=True,
            )

    @music_group.command(
        name="stop", description="Stoppt die Musik und leert die Warteschlange."
    )
    async def stop_track(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            interaction.guild.voice_client.stop()
            self.music_queue = []
            await interaction.response.send_message(
                "Musik gestoppt und Warteschlange geleert.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Zurzeit wird keine Musik abgespielt.", ephemeral=True
            )


async def setup(bot: My_Bot):
    await bot.add_cog(Music(bot))
