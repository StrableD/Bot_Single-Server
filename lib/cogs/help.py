from datetime import date
from typing import Optional, get_args

from discord import Colour, Embed, User
from discord.ext.commands import Cog, Command, Context, check, command
from discord.ext.commands.converter import Greedy
from discord.ext.commands.errors import CheckFailure
from discord.ext.menus import ListPageSource, MenuPages
from discord.utils import find

from lib.bot import My_Bot
from lib.db.db import getChannelID, resetSeason


def is_guild_owner(ctx):
    if ctx.guild is not None:
        return ctx.author.id in (312644293602836482, 273490147645849610)
    else:
        return False


def syntax(cmd: Command):
    cmd_and_aliases = "|".join([str(cmd), *cmd.aliases])
    prefix = ">"

    params = []

    for key, value in cmd.clean_params.items():
        if key not in "args":
            params.append(
                f"[{key}]"
                if None in get_args(value.annotation) or isinstance(value.annotation, Greedy)
                else f"<{key}>"
            )

    params = " ".join(params) if params != [] else "(No Parameters)"

    return f"`{prefix}{cmd_and_aliases} {params}`"


class HelpMenu(ListPageSource):
    def __init__(self, ctx: Context, data):
        self.ctx = ctx

        super().__init__(data, per_page=5)

    async def write_page(self, menu: MenuPages, fields=None):
        if fields is None:
            fields = []
        offset = (menu.current_page * self.per_page) + 1
        len_data = len(self.entries)

        embed = Embed(
            title="Hilfe",
            description="Willkommen bei der Hilfeseite vom Erzähler-Bot!",
            colour=Colour.from_rgb(87, 204, 47),
        )
        embed.set_thumbnail(url=self.ctx.guild.me.avatar.url)
        embed.set_footer(
            text=f"{offset:,} - {min(len_data, offset + self.per_page - 1):,} von {len_data:,} Befehlen."
        )

        for value, name in fields:
            embed.add_field(name=name, value=value, inline=False)

        return embed

    async def format_page(self, menu: MenuPages, entries):
        fields = []

        for entry in entries:
            fields.append((entry.short_doc or "No description", syntax(entry)))

        return await self.write_page(menu, fields)


class Help(Cog):
    def __init__(self, bot: My_Bot):
        self.bot = bot
        self.bot.remove_command("help")

    @staticmethod
    async def cmdHelp(ctx: Context, cmd: Command):
        embed = Embed(
            title=f"Hilfe mit `{cmd}`",
            description=syntax(cmd),
            colour=Colour.from_rgb(87, 204, 47),
        )
        embed.add_field(name="Beschreibung des Befehls", value=cmd.help)
        await ctx.send(embed=embed, delete_after=20.0)

    @command(name="help", aliases=["hilfe"])
    async def showHelp(self, ctx: Context, cmd: Optional[str]):
        """
        Zeigt diese Antwort.
        Wenn es mit einem Befehl zusammen aufgerufen wird, dann gibt es genauere Angaben zurück.
        ``cmd``: Ein spezifischer Befehl (optional)
        """
        if cmd is None:
            commands = []
            for cmd in self.bot.commands:
                if is_guild_owner(ctx):
                    if not cmd.hidden and cmd.enabled:
                        commands.append(cmd)
                else:
                    if (not any(map(lambda f: f == is_guild_owner, cmd.checks))
                            and not cmd.hidden and cmd.enabled):
                        commands.append(cmd)

            def filter(arg):
                if arg.cog_name == "Game":
                    return 1
                elif arg.cog_name == "Settings":
                    return 2
                elif arg.cog_name == "Elo":
                    return 3
                else:
                    return 4

            commands.sort(key=filter)
            menu = MenuPages(
                source=HelpMenu(ctx, commands),
                clear_reactions_after=True,
                delete_message_after=True,
                timeout=60.0,
            )
            await menu.start(ctx)
            await self.bot.wait_for(
                "message_delete", check=lambda m: m.author.id == self.bot.user.id
            )
        else:
            if cmd := find(lambda m: m.name == cmd or cmd in m.aliases, self.bot.commands):
                if any(cmd_check(ctx) for cmd_check in cmd.checks) or cmd.checks == []:
                    await self.cmdHelp(ctx, cmd)
                else:
                    await ctx.send(
                        "Du hast keine Berechtigung diesen Befehl auszuführen.",
                        delete_after=15.0,
                    )
            else:
                await ctx.send(
                    f"Den Befehl `{cmd}` gibt es nicht."
                    f"\nBitte gib den richtigen Befehlsnamen ein, um nähere Infos zu term Befehl zu bekommen.",
                    delete_after=10.0,
                )

    @command(name="invite", aliases=["einladen", "in"])
    @check(is_guild_owner)
    async def invitePlayer(self, ctx: Context, player: User):
        """
        Hiermit kann ein Spieler eingeladen werden.
        Hierfür wird der Discordname und der Diskriminator eingegeben werden.
        ``player``: Der Spieler in Form von Name#Diskriminator
        """
        inviteChannel = ctx.guild.get_channel(getChannelID("invites"))
        invite = await inviteChannel.create_invite(
            max_age=10800,
            max_uses=1,
            reason=f"{ctx.author.display_name} wollte {player.display_name} einladen.",
        )
        await player.send(
            f'{ctx.author.display_name} will dich auf den Server "{ctx.guild.name}" einladen: \n{invite.url}',
            delete_after=10800.0,
        )

    @invitePlayer.error
    async def invitePlayerError(self, ctx: Context, exc):
        if isinstance(exc, CheckFailure):
            await ctx.send(
                f"Du hast keine Berechtigung den Befehl ``{ctx.command.name}`` auszuführen",
                delete_after=20.0,
            )
        else:
            raise exc

    @command(name="newseason", aliases=["season"])
    @check(is_guild_owner)
    async def invitePlayer(self, ctx: Context):
        self.bot._season_date = date.today()
        resetSeason()
        await ctx.send(
            """__Die Saison wurde beendet und eine neue angefangen.__\n
            \nDie gespielten Spiele und die Elo wurden zurückgesetzt""")

    @command(name="update")
    @check(lambda ctx: ctx.author.id == ctx.bot.owner_id)
    async def updateManually(self, ctx: Context):
        self.bot.update_bot()
        await ctx.send("Updated bot successfully", delete_after=10.0)

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("help")


def setup(bot: My_Bot):
    bot.add_cog(Help(bot))
