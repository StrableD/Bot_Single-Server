from typing import Optional
from discord.channel import TextChannel
from lib.bot import My_Bot
from pathlib import Path

from discord import Colour, Embed, Guild, Emoji, Member, embeds
from discord.ext.commands import Cog, Context, command, has_role
from discord.utils import get
from lib.bot.constants import (
    BOTPATH,
    EMOJIS,
    MyRoleConverter,
    getCadre,
    setDefaultCadre,
    setPlayingCadre,
)
from lib.db.db import getChannelID, getRoleID
from num2words import num2words  # type: ignore
from word2number import w2n


async def updateEmojis(guild: Guild, emojis: list[int]):
    returnEmojis = []
    emojisToAdd = []
    for image in Path(BOTPATH + "/data/emojis").glob("*.png"):
        for emoji in emojis:
            if image.name == f"keycap_{num2words(emoji)}.png":
                emojisToAdd.append(image)
                continue
    for emoji in emojisToAdd:
        if emoji.stem not in list(map(lambda m: m.name, guild.emojis)):
            addedEmoji = await guild.create_custom_emoji(
                name=emoji.stem, image=open(emoji, "rb").read()
            )
            returnEmojis.append(addedEmoji)
    return returnEmojis


async def takeSurvey(ctx: Context, theme: str, content: list[tuple]):
    embed = Embed(
        title="Bitte auswählen", description=theme, color=Colour.from_rgb(12, 190, 220)
    )
    emojiNums = []
    for name, value in content:
        if value.isdigit():
            emojiNums.append(int(value))
        else:
            emojiNums.append(content.index((name, value)) + 1)
        embed.add_field(name=name, value=value, inline=True)
    updatedEmojis = await updateEmojis(ctx.guild, emojiNums)
    msg = await ctx.send(embed=embed)
    for emoji in emojiNums:
        if emoji <= 10:
            await msg.add_reaction(EMOJIS[emoji])
        else:
            for guildEmoji in ctx.guild.emojis:
                if guildEmoji.name == f"keycap_{num2words(emoji)}":
                    await msg.add_reaction(guildEmoji)
    reaction, user = await ctx.bot.wait_for(
        "reaction_add",
        check=lambda m, u: (
            str(m) in EMOJIS.values()
            if type(m.emoji) == str
            else m.emoji.name in map(lambda x: f"keycap_{num2words(x)}", emojiNums)
        )
        and not u.bot,
    )
    await msg.delete()
    ctx.bot.emitter.emit("delEmojis", updatedEmojis)
    if str(reaction) in EMOJIS.values():
        for number, string in EMOJIS.items():
            if str(reaction) == string:
                return number
    else:
        reaction = str(reaction.emoji.name)[7:]
        return w2n.word_to_num(reaction)


class Settings(Cog):
    def __init__(self, bot: My_Bot):
        self.bot = bot
        self.bot.emitter.on("delEmojis", self.delEmojis)

    @property
    def cadreLength(self):
        game = self.bot.get_cog("Game")
        return game.cadreLength

    async def getNewCadre(self, ctx: Context):
        content = []
        for channel in ctx.guild.get_channel(
            getChannelID("default_cadre")
        ).text_channels:
            content.append((channel.name, channel.name[:2]))
        cadreSize = await takeSurvey(ctx, "Welche Kadergröße hättest du gerne", content)

        channelName = ""
        for name, number in content:
            if cadreSize == int(number):
                channelName = name
                break
        channel = get(ctx.guild.channels, name=channelName)

        content.clear()
        async for message in channel.history():
            splitMessage = message.content.split("\n")
            value = []
            for row in splitMessage[1:]:
                if "-" in row:
                    break
                value.append(row.strip())
            content.append((splitMessage[0], "\n".join(value)))
        cadreNum = await takeSurvey(ctx, "Welchen der Kader willst du haben?", content)

        squad = content[cadreNum - 1][1]
        squadDict = dict()
        for role in squad.split("\n"):
            role = role.lower()
            if role == "":
                continue
            elif role not in squadDict.keys():
                squadDict[role] = 1
            else:
                squadDict[role] += 1
        return squadDict

    @command(name="standardkader", aliases=["dafaultcadre", "defcadre"])
    @has_role(getRoleID("gamemaster"))
    async def setDefaultCadre(self, ctx: Context):
        """
        Hiermit kannst du den Standard-Kader des Bots festlegen.
        Er wird aus den auf dem Server angegebenen Standard-Kadern ausgewählt.
        Der Standard-Kader wird automatisch für das Spiel ausgewählt, wenn vorher kein anderer ausgewählt wird.
        """
        squadDict = await self.getNewCadre(ctx)

        setDefaultCadre(squadDict)

        embed = Embed(
            title="Der Kader sieht wie folgt aus.", color=Colour.from_rgb(192, 192, 192)
        )
        value = ""
        for role, num in squadDict.items():
            value += f"{str(role).title()}: {num}\n"

        embed.add_field(name=f"{self.cadreLength}er Kader", value=value)
        await ctx.send(embed=embed, delete_after=60.0)

    @command(name="change", aliases=["ändern", "wechseln"])
    @has_role(getRoleID("gamemaster"))
    async def changeCadre(self, ctx: Context, clear: bool = False):
        """
        Hiermit änderst du den aktuellen Spielekader.
        Er wird aus den auf dem Server angegeben Standard-Kadern ausgewählt.
        Wenn dieser nicht eingestellt ist, dann wird der Standard-Kader des Bots verwendet.
        ``clear``: Gibt an, ob der Kader zurückgesetzt wird (optional)
        """
        if clear:
            setPlayingCadre({})
            await ctx.send(
                "Es ist zur Zeit kein Spielekader ausgewählt. Wenn gespielt wird, wird der Standardkader benutzt.",
                delete_after=20.0,
            )
            return

        squadDict = await self.getNewCadre(ctx)

        setPlayingCadre(squadDict)

        embed = Embed(
            title="Der Kader sieht wie folgt aus.", color=Colour.from_rgb(192, 192, 192)
        )
        value = ""
        for role, num in squadDict.items():
            value += f"{str(role).title()}: {num}\n"

        embed.add_field(name=f"{self.cadreLength}er Kader", value=value)
        await ctx.send(embed=embed, delete_after=60.0)

    # last stand with lukas
    @command(name="fill", aliases=["hinzufügen", "add"])
    @has_role(getRoleID("gamemaster"))
    async def addCitizen(self, ctx: Context):
        """
        Zu dem aktuellen Spielekader wird ein Dorfbewohner hinzugefügt.
        Wenn es noch keinen Spielekader gibt, dann wird zu dem Standartkader ein Dorfbewohner hinzugefügt.
        Der Standartkader wird dann zum Spielekader.
        """
        cadre = getCadre()
        if "dorfbewohner" not in cadre:
            cadre["dorfbewohner"] = 1
        else:
            cadre["dorfbewohner"] += 1
        setPlayingCadre(cadre)
        await self.returnCadre(ctx)

    @command(name="minus", aliases=["entfernen", "sub"])
    @has_role(getRoleID("gamemaster"))
    async def removeCitizen(self, ctx: Context):
        """
        Von dem aktuellen Kader wird ein Dorfbewohner entfernt.
        Wenn es noch keinen Spielekader gibt, dann wird zu dem Standartkader ein Dorfbewohner entfernt.
        Der Standartkader wird dann zum Spielekader.
        Wenn es keine Dorfbewohner mehr gibt, dann passiert nichts.
        """
        cadre = getCadre()
        if "dorfbewohner" in cadre:
            cadre["dorfbewohner"] -= 1
            if cadre["dorfbewohner"] < 1:
                del cadre["dorfbewohner"]
                await ctx.send(
                    "Jetzt gibt es keine Dorfbewohner mehr im aktuellen Kader!",
                    delete_after=20.0,
                )
        else:
            await ctx.send(
                "Es gibt keine Dorfbewohner mehr im aktuellen Kader!", delete_after=20.0
            )
        await self.returnCadre(ctx)

    @command(name="cadre", aliases=["kader"])
    async def returnCadre(self, ctx: Context):
        """
        Gibt den aktuellen Kader zurück.
        """
        cadre = getCadre()
        embed = Embed(
            title="Der Kader sieht wie folgt aus.", color=Colour.from_rgb(192, 192, 192)
        )
        value = ""
        for role, num in cadre.items():
            value += f"{str(role).title()}: {num}\n"

        embed.add_field(name=f"{self.cadreLength}er Kader", value=value)
        await ctx.send(embed=embed, delete_after=60.0)

    @command(name="setRole", aliases=["gibRolle", "role"])
    @has_role(getRoleID("gamemaster"))
    async def setPlayerRole(self, ctx: Context, player: Member, role: MyRoleConverter):
        await player.add_roles(role)
        await ctx.send(
            embed=Embed(
                title="Rollen des Spielers",
                description=f"Der Spieler {player.display_name} hat folgende Rollen:",
                color=Colour.random(),
            ).add_field(
                name="Rollen", value="\n".join(map(lambda x: x.name, player.roles))
            ),
            delete_after=100.0,
        )

    @command(name="delete", aliases=["lösche", "del"])
    @has_role(getRoleID("gamemaster"))
    async def deleteMessages(self, ctx: Context, number: Optional[int] = 1, channel: Optional[TextChannel] = None):
        """
        Löscht die angegebene Anzahl an Nachrichten im angegebenen Kanal.
        ```number```: Die Anzahl der Nachrichten. (optional)
        ```channel```: Der Kanal, in dem die Nachrichten gelöscht werden sollen. (optional)
        """
        await ctx.message.delete()
        
        if channel == None:
            channel = ctx.channel
        async for message in channel.history(limit=number, oldest_first=False):
            await message.delete()

        await ctx.send(
            embed=Embed(
                title="Gelöschte Nachrichten", colour=Colour.teal()
            ).add_field(name="Anzahl", value=str(number)),
            delete_after=60.0,
        )

    @command(name="clear", aliases=["aufräumen", "leeren"])
    @has_role(getRoleID("gamemaster"))
    async def clearGameChannels(self, ctx: Context):
        """
        Die Kanäle, in denen gespielt wird, werden aufgeräumt.
        Alle Nachrichten in den Kanälen unterhalb der Kategorie Morbach werden geleert.
        Ausgenommen sind die Bot-Kanäle
        """
        game_category = ctx.guild.get_channel(getChannelID("game_category"))
        bot_channels = tuple(
            ctx.guild.get_channel(getChannelID(x))
            for x in ("bot_channel", "music_channel")
        )
        numMsgs = 0
        
        msg = await ctx.send("Die Nachrichten werden geslöscht.\nDies kann einen Moment dauern.")
        
        for category in filter(
            lambda c: c.position >= game_category.position, ctx.guild.categories
        ):
            for channel in filter(
                lambda c: type(c) == TextChannel and c not in bot_channels,
                category.channels,
            ):
                async for message in channel.history(oldest_first=True):
                    await message.delete()
                    numMsgs += 1
        loveChannel = ctx.guild.get_channel(getChannelID("lovebirds"))
        removed_players= []
        for member in filter(
            lambda memb: type(memb) == Member and memb != ctx.guild.owner,
            loveChannel.overwrites,
        ):
            await loveChannel.set_permissions(member, overwrite=None)
            removed_players.append(member.display_name)
        print(numMsgs)
        
        embed=Embed(
                title="Gelöschte Nachrichten",
                description="Die Kanäle wurden geleert.",
                colour=Colour.teal())
        embed.add_field(name="Anzahl", value=str(numMsgs))
        if removed_players != []:
            embed.add_field(name="Liebespaar", value="\n".join(removed_players))
        await msg.delete()
        await ctx.send(embed = embed,delete_after=100.0)

    async def delEmojis(self, EmojiList: list[Emoji]):
        for emoji in EmojiList:
            await emoji.delete()

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("settings")


def setup(bot):
    bot.add_cog(Settings(bot))
