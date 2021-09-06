from asyncio.tasks import sleep
from datetime import date
from os.path import getmtime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord import Guild, Intents
from discord.channel import DMChannel
from discord.ext.commands import Bot, Context
from discord.ext.commands.core import Command, command
from discord.ext.commands.errors import CommandNotFound
from discord.mentions import AllowedMentions
from discord.message import Message
from lib.bot.constants import BOTPATH, COGS, TOKEN, NoPerms
from lib.db.db import autosave, getChannel
from eventemitter import EventEmitter  # type: ignore

IGNORE_EXCEPTIONS = (CommandNotFound, NoPerms)


class Ready(object):
    def __init__(self):
        for cog in COGS:
            setattr(self, cog, False)

    def ready_up(self, cog):
        setattr(self, cog, True)
        print(f" {cog} cog ready")

    def all_ready(self):
        return all([getattr(self, cog) for cog in COGS])


class My_Bot(Bot):
    def __init__(self):
        self.prefix = ">"
        self.ready = False
        self.cogs_ready = Ready()
        self.update_date = getmtime(BOTPATH + "/lib/bot/update.txt")

        self.guild: Guild = None
        self.scheduler = AsyncIOScheduler()
        self.emitter = EventEmitter()

        self.ghostvoices = False
        self._season_date = date.today()
        self._current_gamemaster = None
        self._lastRound = date(1999, 1, 1)
        self._roundNum = 1

        autosave(self.scheduler)

        super().__init__(
            command_prefix=self.prefix,
            owner_id=312644293602836482,
            intents=Intents.all(),
        )

    def setup(self):
        for cog in COGS:
            self.load_extension(f"lib.cogs.{cog}")
            print(f" {cog} cog loaded")

        print("setup complete")

    async def printUpdateTxt(self, updateTxt: str):
        await self.guild.get_channel(getChannel("bot_channel")).send(
            updateTxt, allowed_mentions=AllowedMentions.all()
        )

    def update_bot(self):
        cogs = self.cogs.copy()
        for cog_name in cogs.keys():
            self.reload_extension("lib.cogs." + cog_name.lower())
        if self.update_date < getmtime(BOTPATH + "/lib/bot/update.txt"):
            with open(BOTPATH + "/lib/bot/update.txt", "r") as updatefile:
                updateTxt = updatefile.read()
            self.emitter.emit("bot_update", updateTxt)
            self.update_date = getmtime(BOTPATH + "/lib/bot/update.txt")

    def run(self):
        print("running setup...")
        self.setup()

        super().run(TOKEN, reconnect=True)
        print("bot is running...")

    async def process_commands(self, message: Message):
        ctx = await self.get_context(message, cls=Context)

        if ctx.command is not None and ctx.guild is not None:
            if not self.ready:
                await ctx.send(
                    "Wait a second, I'm not ready to process commands yet",
                    delete_after=20.0,
                )
            else:
                await self.invoke(ctx)

    async def process_ghostvoices(self, messsage: Message):
        if self.ghostvoices:
            channel = self.get_channel(getChannel("ghostvoices"))
            msg = f"Von {messsage.author.display_name}: \n"
            msg += f'"{messsage.content}"'
            await channel.send(msg) if channel != None else await self.get_user(
                self.owner_id
            ).send("Die Geisterstimme konnte nicht gesendet werden")

    async def on_connect(self):
        print("bot connected")

    async def on_disconnect(self):
        print("bot disconnected")

    async def on_error(self, err, *args, **kwargs):
        if err == "on_command_error" and args[0].command.name not in ("invite", "elo"):
            await args[0].send("Command Error", delete_after=15.0)

        print("An Error occurred")
        raise  # type: ignore

    async def on_command_error(self, ctx, exc):
        if any([isinstance(exc, error) for error in IGNORE_EXCEPTIONS]):
            pass
        elif hasattr(exc, "original"):
            raise exc.original
        else:
            raise exc

    async def on_ready(self):
        if not self.ready:
            self.guild = self.get_guild(768494431124586546)
            self.scheduler.start()
            self.scheduler.add_job(
                self.update_bot, CronTrigger(day_of_week=3, hour=5, minute=0, second=0)
            )
            self.emitter.on("bot_update", self.printUpdateTxt)

            while not self.cogs_ready.all_ready():
                await sleep(0.5)

            self.ready = True
            print("bot is ready")
        else:
            print("bot reconnected")

    async def on_message(self, message: Message):
        if not message.author.bot:
            if not isinstance(message.channel, DMChannel):
                await self.process_commands(message)
            elif isinstance(message.channel, DMChannel):
                await self.process_ghostvoices(message)
 
bot = My_Bot()