import logging
import logging.config
import json
import os
from asyncio.tasks import sleep
from datetime import date
from os.path import getmtime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord import Guild, Intents, app_commands
from discord.channel import DMChannel, TextChannel
from discord.errors import NotFound
from discord.ext.commands import Bot, Context
from discord.ext.commands.errors import CommandNotFound
from discord.mentions import AllowedMentions
from discord.message import Message
from pyee.asyncio import AsyncIOEventEmitter

from lib.db.db import autosave, getChannelID, updateMembers, AsyncSessionLocal, build
from lib.db.models import BotState
from sqlalchemy import select, update
from lib.helper.constants import BOTPATH, COGS, TOKEN
from lib.helper.utils import member_to_json, MemberJsonDecoder
from lib.helper.errors import NoPerms

IGNORE_EXCEPTIONS = (CommandNotFound, NoPerms)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        'default': {
            "class": "logging.Formatter",
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s'
        }
    },
    "handlers": {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'level': 'INFO'
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO"
    }
}
logging.config.dictConfig(LOGGING)

class Ready(object):
    def __init__(self):
        for cog in COGS:
            setattr(self, cog, False)

    def ready_up(self, cog):
        setattr(self, cog, True)
        bot.logger.info(f" {cog} cog ready")

    def all_ready(self):
        return all([getattr(self, cog) for cog in COGS])

class My_Bot(Bot):
    def __init__(self):
        guild_ids = [int(g) for g in os.getenv("GUILD_IDS", "").split(",") if g]
        super().__init__(
            command_prefix=">",
            owner_id=312644293602836482,
            intents=Intents.all(),
            debug_guilds=guild_ids if guild_ids else None,
            case_insensitive=True
        )

        self.ready = False
        self.cogs_ready = Ready()
        self._update_date = getmtime(BOTPATH + "/lib/bot/update.txt") if os.path.exists(BOTPATH + "/lib/bot/update.txt") else 0

        self.guild: Guild = None
        self.scheduler = AsyncIOScheduler()
        self.emitter = AsyncIOEventEmitter()
        self.logger = logging.getLogger("My_Bot")

        self._ghostvoices = False
        self._season_date = date.today()
        self._current_gamemaster = None
        self._lastRound = date(1999, 1, 1)
        self._roundNum = 1

        self.bot_attr = {"_update_date", "_ghostvoices", "_season_date", "_current_gamemaster", "_lastRound", "_roundNum"}

        autosave(self.scheduler)

    async def setup_hook(self):
        await build() # Initialize SQLAlchemy ORM schema
        for cog in COGS:
            try:
                await self.load_extension(f"lib.cogs.{cog}")
                self.logger.info(f"{cog} cog loaded")
            except Exception as e:
                self.logger.error(f"Failed to load {cog}: {e}")

        await self.tree.sync()
        self.logger.info("setup complete")

    async def update_bot(self):
        pass

    def run(self):
        super().run(TOKEN, reconnect=True)

    async def process_commands(self, message: Message):
        ctx = await self.get_context(message, cls=Context)
        if ctx.command is not None and ctx.guild is not None:
            if not self.ready:
                await ctx.send("Wait a second, I'm not ready to process commands yet", delete_after=20.0)
            else:
                try:
                    await ctx.message.delete()
                except NotFound:
                    pass
                await self.invoke(ctx)

    async def on_connect(self):
        self.logger.info("bot connected")
        self.guild = self.guilds[0] if self.guilds else None
        await self.update_bot_attr()
        self.logger.info("old bot data loaded")

    async def on_disconnect(self):
        self.logger.info("bot disconnected")
        await self.update_json_attr()

    async def on_command_error(self, ctx, exc):
        if any([isinstance(exc, error) for error in IGNORE_EXCEPTIONS]):
            pass
        elif hasattr(exc, "original"):
            raise exc.original
        else:
            raise exc

    async def on_ready(self):
        if not self.ready:
            self.logger.info("bot reading up...")
            self.scheduler.start()
            self.scheduler.add_job(
                self.update_bot, CronTrigger(day_of_week=3, hour=5, minute=0, second=0)
            )

            if self.guild:
                await updateMembers(list(filter(lambda x: not x.bot, self.guild.members)))

            while not self.cogs_ready.all_ready():
                await sleep(0.5)

            self.ready = True
            self.logger.info("bot is ready")
        else:
            self.logger.info("bot reconnected")

    async def on_message(self, message: Message):
        if not message.author.bot:
            if not isinstance(message.channel, DMChannel):
                await self.process_commands(message)
        await super().on_message(message)

    async def update_json_attr(self):
        attr_dict = {}
        for attr in self.bot_attr:
            val = getattr(self, attr, None)
            if isinstance(val, date):
                attr_dict[attr] = val.isoformat()
            else:
                attr_dict[attr] = val
        
        member_attr_dict = member_to_json(attr_dict)
        json_data = json.dumps(member_attr_dict)
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(BotState).where(BotState.key == 'bot_attributes'))
            state = result.scalar_one_or_none()
            if state:
                state.value = json_data
            else:
                session.add(BotState(key='bot_attributes', value=json_data))
            await session.commit()

    async def update_bot_attr(self):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(BotState).where(BotState.key == 'bot_attributes'))
            state = result.scalar_one_or_none()
            if state and state.value:
                attr_dict = MemberJsonDecoder(guild=self.guild).decode(state.value)
                for attr, value in attr_dict.items():
                    if attr in ("_season_date", "_lastRound") and isinstance(value, str):
                        try:
                            value = date.fromisoformat(value)
                        except ValueError:
                            pass
                    setattr(self, attr, value)

bot = My_Bot()
