import logging
import logging.config
from asyncio.tasks import sleep
from datetime import date
from os.path import getmtime

import toml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord import Guild, Intents
from discord.channel import DMChannel, TextChannel
from discord.errors import NotFound
from discord.ext.commands import Bot, Context, when_mentioned_or
from discord.ext.commands.errors import CommandNotFound
from discord.mentions import AllowedMentions
from discord.message import Message
from pyee import AsyncIOEventEmitter  # type: ignore

from lib.db.db import autosave, getChannelID, updateMembers
from lib.helper.constants import BOTPATH, COGS, TOKEN, MemberJsonDecoder, member_to_json, myGuild, NoPerms

IGNORE_EXCEPTIONS = (CommandNotFound, NoPerms)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        'default': {
            "class": "logging.Formatter",
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s'
        },
        "error": {
            "class": "logging.Formatter",
            "format": "[%(levelname)s] %(asctime)s %(module)s.%(funcName)s [%(lineno)d]: %(message)s\n",
            "datefmt": "%d.%M.%Y %H:%M:%S"
        },
        "info": {
            "class": "logging.Formatter",
            "format": "[%(levelname)s] %(asctime)s %(command)s [%(author)s]: %(message)s",
            "datefmt": "%d.%M.%Y %H:%M:%S"
        },
    },
    "filters": {
        "info_filter": {
            "()": "ext://lib.helper.constants.LogFilter",
        }
    },
    "handlers": {
        "err_file": {
            "class": "logging.FileHandler",
            "level": "WARNING",
            "encoding": "UTF-8",
            "formatter": "error",
            "filename": BOTPATH + f"/logs/errors/error_{date.today()}.log",
            "mode": "a"
        },
        "info_file": {
            "class": "logging.FileHandler",
            "level": "INFO",
            "encoding": "UTF-8",
            "formatter": "info",
            "filters": ["info_filter", ],
            "filename": BOTPATH + f"/logs/infos/infos_{date.today()}.log",
            "mode": "a"
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'level': 'INFO',
            "filters": ["info_filter", ]
        },
    },
    "loggers": {
        "Error_Logger": {
            "handlers": ["err_file", "info_file"]
        }
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
        bot.logger.info(f" {cog} cog ready", extra={"command": "ready_up", "author": "func"})

    def all_ready(self):
        return all([getattr(self, cog) for cog in COGS])


class My_Bot(Bot):
    def __init__(self):
        super().__init__(
            command_prefix=when_mentioned_or(">"),
            owner_id=312644293602836482,
            intents=Intents.all(),
            debug_guilds=[768494431124586546, 922606655085105163],
            case_insensitive=True
        )

        self.ready = False
        self.cogs_ready = Ready()
        self._update_date = getmtime(BOTPATH + "/lib/bot/update.txt")

        self.guild: Guild = None
        self.scheduler = AsyncIOScheduler()
        self.emitter = AsyncIOEventEmitter()
        self.logger = logging.getLogger("Error_Logger")

        self._ghostvoices = False
        self._season_date = date.today()
        self._current_gamemaster = None
        self._lastRound = date(1999, 1, 1)
        self._roundNum = 1

        autosave(self.scheduler)

    def setup(self):
        for cog in COGS:
            self.load_extension(f"lib.cogs.{cog}", store=False)
            self.logger.info(f" {cog} cog loaded", extra={"command": "setup", "author": "func"})

        self.logger.info("setup complete", extra={"command": "setup", "author": "func"})

    async def printUpdateTxt(self, updateTxt: str):
        bot_channel: TextChannel = self.guild.get_channel(getChannelID("bot_channel"))
        async with bot_channel.typing():
            await bot_channel.send(content=updateTxt, allowed_mentions=AllowedMentions.all())

    def update_bot(self):
        cogs = dict(self.cogs).copy()
        for cog_name in cogs.keys():
            self.reload_extension("lib.cogs." + cog_name.lower())
        if self._update_date < getmtime(BOTPATH + "/lib/bot/update.txt"):
            with open(BOTPATH + "/lib/bot/update.txt", "r", encoding="utf-8") as updatefile:
                updateTxt = updatefile.read()
            self.emitter.emit("bot_update", updateTxt)
            self._update_date = getmtime(BOTPATH + "/lib/bot/update.txt")
        updateMembers(list(filter(lambda x: not x.bot, self.guild.members)))
        self.update_json_attr()

    def run(self):
        self.logger.info("running setup...", extra={"command": "run", "author": "func"})
        self.setup()

        super().run(TOKEN, reconnect=True)
        self.update_json_attr()
        self.logger.info("bot crashed...", extra={"command": "run", "author": "func"})

    async def process_commands(self, message: Message):
        ctx = await self.get_context(message, cls=Context)

        if ctx.command is not None and ctx.guild is not None:
            if not self.ready:
                await ctx.send(
                    "Wait a second, I'm not ready to process commands yet",
                    delete_after=20.0,
                )
            else:
                self.logger.info(f"Es wurde ein Befehl ausgeführt im Kanal '{ctx.channel.name}'",
                                 extra={"command": ctx.command, "author": ctx.author.display_name})
                try:
                    await ctx.message.delete()
                except NotFound:
                    pass
                await self.invoke(ctx)

    async def process_ghostvoices(self, message: Message):
        if self._ghostvoices:
            channel = self.get_channel(getChannelID("ghostvoices"))
            msg = f"Von {message.author.display_name}: \n"
            msg += f'"{message.content}"'
            await channel.send(msg) if channel is not None else await self.get_user(
                self.owner_id
            ).send("Die Geisterstimme konnte nicht gesendet werden")
            self.logger.info(f'Es wurde eine Geisterstimme abgegeben: "{message.content}"',
                             extra={"command": "Geisterstimme", "author": message.author.display_name})

    async def on_connect(self):
        await super().on_connect()
        self.logger.info("bot connected", extra={"command": "on_connect", "author": "func"})
        self.update_bot_attr()

    async def on_disconnect(self):
        self.logger.info("bot disconnected", extra={"command": "on_disconnect", "author": "func"})
        self.update_json_attr()

    async def on_error(self, err, *args):
        if err == "on_command_error" and args[0].command.name not in ("invite", "elo", "chronicle"):
            await args[0].send("Command Error", delete_after=15.0)

        if len(args) > 1:
            self.logger.warning(f"An Error occurred: {args[1]}")
        elif len(args) == 1:
            self.logger.warning(f"An Error occurred: {args[0]}")
        else:
            self.logger.warning(f"An Error occurred")
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
            myGuild.guild = self.guild
            self.scheduler.start()
            self.scheduler.add_job(
                self.update_bot, CronTrigger(day_of_week=3, hour=5, minute=0, second=0)
            )
            self.emitter.on("bot_update", self.printUpdateTxt)

            self.logger.info("updating the members", extra={"command": "on_ready", "author": "func"})
            updateMembers(list(filter(lambda x: not x.bot, self.guild.members)))

            while not self.cogs_ready.all_ready():
                await sleep(0.5)

            self.ready = True
            self.logger.info("bot is ready", extra={"command": "on_ready", "author": "func"})
        else:
            self.logger.info("bot reconnected", extra={"command": "on_ready", "author": "func"})

    async def on_message(self, message: Message):
        if not message.author.bot:
            if not isinstance(message.channel, DMChannel):
                await self.process_commands(message)
            elif isinstance(message.channel, DMChannel):
                await self.process_ghostvoices(message)

    def update_json_attr(self):
        attr_dir = list(self.__dir__())
        attr_dir = attr_dir[:attr_dir.index("all_commands")]
        attr_dir = list(filter(lambda x: x.startswith("_"), attr_dir))
        with open(BOTPATH + "/data/bot_attributes.toml", "r") as attr_file:
            attr_dict = toml.load(attr_file)
        for attr in attr_dir:
            attr_dict["attributes"][attr] = self.__getattribute__(attr)
        attr_dict = member_to_json(attr_dict)
        with open(BOTPATH + "/data/bot_attributes.toml", "w") as attr_file:
            toml.dump(attr_dict, attr_file)

    def update_bot_attr(self):
        with open(BOTPATH + "/data/bot_attributes.toml", "r") as attr_file:
            attr_dict = toml.load(attr_file)
        attr_dict = MemberJsonDecoder().object_hook(attr_dict["attributes"])
        for attr, value in attr_dict.items():
            self.__setattr__(attr, value)


bot = My_Bot()
