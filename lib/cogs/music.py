from discord import utils, FFmpegPCMAudio
from discord.errors import ClientException
from discord.ext.commands import Cog
from discord.ext.commands.context import Context
from discord.ext.commands.core import command
from lib.bot import My_Bot
from youtube_dl import YoutubeDL

class Music(Cog):
    """
    Das Modul, welches die Musikunterstützung zu dem Bot hinzufügt.
    """
    def __init__(self, bot: My_Bot):
        self.bot = bot
        self.voice_channel = None
        
        self.is_playing = False
        
        self.music_queue = []
        self.YDL_OPTIONS = {"format": "bestaudio", "noplaylist": True}
        self.FFMPEG_OPTIONS = {"before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", "options": "-vn"}
        
    def search_yt(self, item):
        with YoutubeDL(self.YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(f"ytsearch:{item}", download=False)["entries"][0]
            except:
                return False
        return {"source": info["formats"][0]["url"], "title": info["title"]}
    
    def play_next(self):
        if len(self.music_queue) > 0:
            self.is_playing = True
            
            m_url = self.music_queue.pop(0)[0]["source"]
            
            self.voice_channel.play(FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS), after=lambda e: self.play_next())
        else:
            self.is_playing = False
    
    async def play_music(self):
        if len(self.music_queue) > 0:
            self.is_playing = True
            
        
    @command(name="play", hidden = True)
    async def play_track(self, ctx: Context, *urls: str):
        pass
    
    @command(name="join", hidden=True)
    async def join_channel(self, ctx: Context):
        if ctx.author.voice == None:
            await ctx.send("Du musst mit einem Sprachkanal verbunden sein", delete_after=30.0)
            raise ConnectionError("Your not connected to a voice channel")
        voiceChannel = ctx.author.voice.channel
        if self.voice(ctx) == None:
            await voiceChannel.connect()
        elif not self.voice(ctx).is_connected() and self.voice(ctx).channel != voiceChannel:
            await voiceChannel.connect()
    
    @command(name="leave", hidden = True)
    async def leave_channel(self, ctx: Context):
        if self.voice(ctx).is_connected():
            await self.voice(ctx).disconnect()
        else:
            await ctx.send("Der Bot ist in keinem Sprachkanal.", delete_after=30.0)
    
    @command(name="pause", hidden=True)
    async def pause_track(self, ctx: Context):
        if self.voice(ctx).is_playing():
            self.voice(ctx).pause()
        else:
            await ctx.send("Zurzeit wird keine Musik abgespielt.", delete_after=30.0)
    
    @command(name="resume", hidden=True)
    async def resume_track(self, ctx: Context):
        if self.voice(ctx).is_paused():
            self.voice(ctx).resume()
        else:
            await ctx.send("Es wird noch Musik gespielt", delete_after=30.0)
    
    @command(name="stop", hidden=True)
    async def stop_track(self, ctx: Context):
        self.voice(ctx).stop()
    
    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("music")

def setup(bot: My_Bot):
    bot.add_cog(Music(bot))