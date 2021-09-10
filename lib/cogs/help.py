from datetime import date
from discord.ext.commands.errors import CheckFailure
from lib.db.db import getChannelID, resetSeason
from typing import Optional, get_args

from discord import Colour, Embed, User
from discord.ext.commands import Bot, Cog, Command, command, Context, check
from discord.ext.commands.converter import _Greedy
from discord.ext.menus import ListPageSource, MenuPages
from discord.utils import find


def is_guild_owner(ctx):
    if ctx.guild != None:
        return ctx.author.id in (273490147645849610,273490147645849610)
    else:
        return False


def syntax(command: Command):
    cmd_and_aliases = "|".join([str(command), *command.aliases])
    prefix = ">"

    params = []

    for key, value in command.clean_params.items():
        if key not in ("args"):
            params.append(
                f"[{key}]"
                if None in get_args(value.annotation)
                or isinstance(value.annotation, _Greedy)
                else f"<{key}>"
            )

    params = " ".join(params) if params != [] else "(No Parameters)"

    return f"`{prefix}{cmd_and_aliases} {params}`"


class HelpMenu(ListPageSource):
    def __init__(self, ctx: Context, data):
        self.ctx = ctx

        super().__init__(data, per_page=5)

    async def write_page(self, menu, fields=[]):
        offset = (menu.current_page * self.per_page) + 1
        len_data = len(self.entries)

        embed = Embed(
            title="Hilfe",
            description="Wilkommen bei der Hilfeseite vom Erzähler-Bot!",
            colour=Colour.from_rgb(87, 204, 47),
        )
        embed.set_thumbnail(url=self.ctx.guild.me.avatar_url)
        embed.set_footer(
            text=f"{offset:,} - {min(len_data, offset+self.per_page-1):,} von {len_data:,} Befehlen."
        )

        for value, name in fields:
            embed.add_field(name=name, value=value, inline=False)

        return embed

    async def format_page(self, menu, entries):
        fields = []

        for entry in entries:
            fields.append((entry.short_doc or "No description", syntax(entry)))

        return await self.write_page(menu, fields)


class Help(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.bot.remove_command("help")

    async def cmdHelp(self, ctx: Context, command: Command):
        embed = Embed(
            title=f"Hilfe mit `{command}`",
            description=syntax(command),
            colour=Colour.from_rgb(87, 204, 47),
        )
        embed.add_field(name="Bescheibung des Befehls", value=command.help)
        await ctx.send(embed=embed, delete_after=20.0)

    @command(name="help", aliases=["hilfe"])
    async def showHelp(self, ctx: Context, cmd: Optional[str]):
        """
        Zeigt diese Antowort.
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
            res = await self.bot.wait_for(
                "message_delete", check=lambda m: m.author.id == self.bot.user.id
            )
            await ctx.message.delete()
        else:
            if command := find(lambda m: m.name == cmd or cmd in m.aliases, self.bot.commands):
                if any(check(ctx) for check in command.checks) or command.checks == []:
                    await self.cmdHelp(ctx, command)
                else:
                    await ctx.send(
                        "Du hast keine Berechtigung diesen Befehl auszuführen.",
                        delete_after=15.0,
                    )
                await ctx.message.delete()
            else:
                await ctx.send(
                    f"Den Befehl `{cmd}` gibt es nicht. \nBitte gib den richtigen Befehlsnamen ein, um nähere Infos zu derm Befehl zu bekommen.",
                    delete_after=10.0,
                )
                await ctx.message.delete()

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
            f'{ctx.author.display_name} will dich in die Guilde "{ctx.guild.name}" einladen: \n{invite.url}',
            delete_after=10800.0,
        )
        await ctx.message.delete()

    @invitePlayer.error
    async def invitePlayerError(self, ctx: Context, exc):
        if isinstance(exc, CheckFailure):
            await ctx.send(
                f"Du hast keine Berechtigung den Befehl ``{ctx.command.name}`` auszuführen",
                delete_after=20.0,
            )
            await ctx.message.delete()
        else:
            raise exc

    @command(name="newseason", aliases=["season"])
    @check(is_guild_owner)
    async def invitePlayer(self, ctx: Context):
        self.bot._season_date = date.today()
        resetSeason()
        await ctx.send("""__Die Saison wurde beendet und eine neue angefangen.__\n\nDie gespielten Spiele und die Elo wurden zurückgesetzt""")
        await ctx.message.delete()

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("help")


def setup(bot):
    bot.add_cog(Help(bot))
