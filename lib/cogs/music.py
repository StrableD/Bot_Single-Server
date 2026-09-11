import os
import asyncio
from discord import FFmpegPCMAudio
from discord.ext import commands
from discord.ext.commands import Cog
from discord.ext.commands.context import Context
import yt_dlp

from lib.bot import My_Bot
from lib.helper.constants import BOTPATH

CACHE_DIR = os.path.join(BOTPATH, "data", "music_cache")
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

class Music(Cog):
    """
    Das Modul, welches die Musikunterstützung zu dem Bot hinzufügt.
    """

    def __init__(self, bot: My_Bot):
        self.bot = bot
        self.voice_channel = None
        self.is_playing = False
        self.music_queue = []
        
        self.YDL_OPTIONS = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(CACHE_DIR, '%(id)s.%(ext)s'),
            'noplaylist': True,
            'quiet': True,
        }
        self.FFMPEG_OPTIONS = {'options': '-vn'}

    async def search_and_download(self, item):
        loop = asyncio.get_event_loop()
        def download():
            with yt_dlp.YoutubeDL(self.YDL_OPTIONS) as ydl:
                try:
                    info = ydl.extract_info(f"ytsearch:{item}", download=True)
                    if 'entries' in info:
                        info = info['entries'][0]
                    filename = ydl.prepare_filename(info)
                    return {"source": filename, "title": info["title"]}
                except Exception as e:
                    print(e)
                    return False
        return await loop.run_in_executor(None, download)

    def play_next(self, ctx):
        if len(self.music_queue) > 0:
            self.is_playing = True
            m_url = self.music_queue.pop(0)["source"]
            self.voice(ctx).play(FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS), after=lambda e: self.play_next(ctx))
        else:
            self.is_playing = False

    def voice(self, ctx):
        return ctx.message.guild.voice_client

    @commands.hybrid_command(name="play", hidden=True)
    async def play_track(self, ctx: Context, *, search: str):
        """Spielt Musik von YouTube ab."""
        await ctx.send("Suche und lade herunter...", ephemeral=True)
        song = await self.search_and_download(search)
        if type(song) == type(True):
            await ctx.send("Konnte das Lied nicht finden oder herunterladen.", ephemeral=True)
        else:
            await ctx.send(f"Zur Warteschlange hinzugefügt: {song['title']}")
            self.music_queue.append(song)
            
            if not self.is_playing:
                await ctx.invoke(self.join_channel)
                self.play_next(ctx)

    @commands.hybrid_command(name="join", hidden=True)
    async def join_channel(self, ctx: Context):
        if ctx.author.voice is None:
            await ctx.send("Du musst mit einem Sprachkanal verbunden sein", delete_after=30.0)
            raise ConnectionError("Your not connected to a voice channel")
        voiceChannel = ctx.author.voice.channel
        if self.voice(ctx) is None:
            await voiceChannel.connect()
        elif not self.voice(ctx).is_connected() and self.voice(ctx).channel != voiceChannel:
            await voiceChannel.connect()

    @commands.hybrid_command(name="leave", hidden=True)
    async def leave_channel(self, ctx: Context):
        if self.voice(ctx) and self.voice(ctx).is_connected():
            await self.voice(ctx).disconnect()
        else:
            await ctx.send("Der Bot ist in keinem Sprachkanal.", delete_after=30.0)

    @commands.hybrid_command(name="pause", hidden=True)
    async def pause_track(self, ctx: Context):
        if self.voice(ctx) and self.voice(ctx).is_playing():
            self.voice(ctx).pause()
            await ctx.send("Musik pausiert.")
        else:
            await ctx.send("Zurzeit wird keine Musik abgespielt.", delete_after=30.0)

    @commands.hybrid_command(name="resume", hidden=True)
    async def resume_track(self, ctx: Context):
        if self.voice(ctx) and self.voice(ctx).is_paused():
            self.voice(ctx).resume()
            await ctx.send("Musik fortgesetzt.")
        else:
            await ctx.send("Es wird noch Musik gespielt", delete_after=30.0)

    @commands.hybrid_command(name="stop", hidden=True)
    async def stop_track(self, ctx: Context):
        if self.voice(ctx):
            self.voice(ctx).stop()
            self.music_queue = []
            await ctx.send("Musik gestoppt und Warteschlange geleert.")

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("music")

async def setup(bot: My_Bot):
    await bot.add_cog(Music(bot))
