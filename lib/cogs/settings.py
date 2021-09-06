from lib.bot import My_Bot
from pathlib import Path

from discord import Colour, Embed, Guild, Emoji
from discord.ext.commands import Cog, Context, command, has_role
from discord.utils import get
from lib.bot.constants import (
    BOTPATH,
    EMOJIS,
    getCadre,
    setDefaultCadre,
    setPlayingCadre,
)
from lib.db.db import getChannel, getRole
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
    embed = Embed(title="Bitte auswählen", description=theme, color=Colour.random())
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
        reaction = str(reaction.emoji.name).strip("keycap_")
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
        for channel in ctx.guild.get_channel(getChannel("default_cadre")).text_channels:
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
    @has_role(getRole("gamemaster"))
    async def setDefaultCadre(self, ctx: Context):
        """
        Hiermit kannst du den Standard-Kader des Bots festlegen.
        Er wird aus den auf dem Server angegebenen Standard-Kadern ausgewählt.
        Der Standard-Kader wird automatisch für das Spiel ausgewählt, wenn vorher kein anderer ausgewählt wird.
        """
        squadDict = await self.getNewCadre(ctx)

        setDefaultCadre(squadDict)

        await ctx.message.delete()
        embed = Embed(title="Der Kader sieht wie folgt aus.", color=Colour.random())
        value = ""
        for role, num in squadDict.items():
            value += f"{str(role).title()}: {num}\n"

        embed.add_field(name=f"{self.cadreLength}er Kader", value=value)
        await ctx.send(embed=embed, delete_after=60.0)

    @command(name="change", aliases=["ändern", "wechseln"])
    @has_role(getRole("gamemaster"))
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
            await ctx.message.delete()
            return
        
        squadDict = await self.getNewCadre(ctx)

        setPlayingCadre(squadDict)

        await ctx.message.delete()
        embed = Embed(title="Der Kader sieht wie folgt aus.", color=Colour.random())
        value = ""
        for role, num in squadDict.items():
            value += f"{str(role).title()}: {num}\n"

        embed.add_field(name=f"{self.cadreLength}er Kader", value=value)
        await ctx.send(embed=embed, delete_after=60.0)

    # last stand with lukas
    @command(name="fill", aliases=["hinzufügen", "add"])
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
        embed = Embed(title="Der Kader sieht wie folgt aus.", color=Colour.random())
        value = ""
        for role, num in cadre.items():
            value += f"{str(role).title()}: {num}\n"

        embed.add_field(name=f"{self.cadreLength}er Kader", value=value)
        await ctx.send(embed=embed, delete_after=60.0)
        await ctx.message.delete()

    async def delEmojis(self, EmojiList: list[Emoji]):
        for emoji in EmojiList:
            await emoji.delete()

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("settings")


def setup(bot):
    bot.add_cog(Settings(bot))
