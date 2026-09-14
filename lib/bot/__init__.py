import logging
import logging.config
import json
import os
from asyncio.tasks import sleep
from datetime import date
from os.path import getmtime


from discord import Guild, Intents, app_commands
from discord.channel import DMChannel, TextChannel

from discord.ext.commands import Bot

from discord.mentions import AllowedMentions
from discord.message import Message
from pyee.asyncio import AsyncIOEventEmitter

from lib.db.db import getChannelID, updateMembers, AsyncSessionLocal, build

from sqlalchemy import select, update
from lib.helper.constants import BOTPATH, COGS, TOKEN

from lib.helper.errors import NoPerms



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


        self.guild: Guild = None

        self.emitter = AsyncIOEventEmitter()
        self.logger = logging.getLogger("My_Bot")





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



    def run(self):
        super().run(TOKEN, reconnect=True)



    async def on_connect(self):
        self.logger.info("bot connected")
        self.guild = self.guilds[0] if self.guilds else None

    async def on_disconnect(self):
        self.logger.info("bot disconnected")



    async def on_ready(self):
        if not self.ready:
            self.logger.info("bot reading up...")

            if self.guild:
                await updateMembers(list(filter(lambda x: not x.bot, self.guild.members)))

            while not self.cogs_ready.all_ready():
                await sleep(0.5)

            self.ready = True
            self.logger.info("bot is ready")
        else:
            self.logger.info("bot reconnected")







bot = My_Bot()
