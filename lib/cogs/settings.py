from pathlib import Path
from typing import Optional

import discord
from discord import Colour, Embed, Guild, Emoji, Member, app_commands
from discord.channel import TextChannel
from discord.ext import commands
from discord.ext.commands import Cog
from discord.utils import get
from num2words import num2words  # type: ignore
from word2number import w2n

from lib.bot import My_Bot
from lib.db.db import getChannelID, getRoleID
from lib.helper.checks import is_gamemaster
from lib.helper.constants import BOTPATH, EMOJIS
from lib.db.cadre_db import getCadre, setDefaultCadre, setPlayingCadre


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


async def takeSurvey(interaction: discord.Interaction, theme: str, content: list[tuple]):
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
    updatedEmojis = await updateEmojis(interaction.guild, emojiNums)
    
    # We must send a message that can take reactions
    if interaction.response.is_done():
        msg = await interaction.followup.send(embed=embed, wait=True)
    else:
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

    for emoji in emojiNums:
        if emoji <= 10:
            await msg.add_reaction(EMOJIS[emoji])
        else:
            for guildEmoji in interaction.guild.emojis:
                if guildEmoji.name == f"keycap_{num2words(emoji)}":
                    await msg.add_reaction(guildEmoji)
    reaction, user = await interaction.client.wait_for(
        "reaction_add",
        check=lambda m, u: (str(m) in EMOJIS.values() if type(m.emoji) == str else m.emoji.name in map(lambda x: f"keycap_{num2words(x)}", emojiNums)) and not u.bot,
    )
    await msg.delete()
    interaction.client.emitter.emit("delEmojis", updatedEmojis)
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

    cadre_group = app_commands.Group(name="cadre", description="Cadre management")

    async def cadreLength(self):
        from lib.db.cadre_db import getCadre
        cadre = await getCadre()
        length = 0
        for num in cadre.values():
            length += num
        return length

    @staticmethod
    async def getNewCadre(interaction: discord.Interaction):
        content = []
        for channel in interaction.guild.get_channel(
                await getChannelID("default_cadre")
        ).text_channels:
            content.append((channel.name, channel.name[:2]))
        cadreSize = await takeSurvey(interaction, "Welche Kadergröße hättest du gerne", content)

        channelName = ""
        for name, number in content:
            if cadreSize == int(number.strip(" -")):
                channelName = name
                break
        channel = get(interaction.guild.channels, name=channelName)

        content.clear()
        async for message in channel.history():
            splitMessage = message.content.split("\n")
            value = []
            for row in splitMessage[1:]:
                if "-" in row:
                    break
                value.append(row.strip())
            content.append((splitMessage[0], "\n".join(value)))
        cadreNum = await takeSurvey(interaction, "Welchen der Kader willst du haben?", content)

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

    @cadre_group.command(name="standardkader", description="Legt den Standard-Kader fest.")
    @is_gamemaster()
    async def setDefaultCadre(self, interaction: discord.Interaction):
        """
        Hiermit kannst du den Standard-Kader des Bots festlegen.
        Er wird aus den auf dem Server angegebenen Standard-Kadern ausgewählt.
        Der Standard-Kader wird automatisch für das Spiel ausgewählt, wenn vorher kein anderer ausgewählt wird.
        """
        await interaction.response.defer(ephemeral=True)
        squadDict = await self.getNewCadre(interaction)

        await setDefaultCadre(squadDict)

        embed = Embed(
            title="Der Kader sieht wie folgt aus.", color=Colour.from_rgb(192, 192, 192)
        )
        value = ""
        for role, num in squadDict.items():
            value += f"{str(role).title()}: {num}\n"

        embed.add_field(name=f"{await self.cadreLength()}er Kader", value=value)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @cadre_group.command(name="change", description="Ändert den aktuellen Spielekader.")
    @app_commands.describe(clear="Gibt an, ob der Kader zurückgesetzt wird")
    @is_gamemaster()
    async def changeCadre(self, interaction: discord.Interaction, clear: Optional[str] = None):
        """
        Hiermit änderst du den aktuellen Spielekader.
        Er wird aus den auf dem Server angegeben Standard-Kadern ausgewählt.
        Wenn dieser nicht eingestellt ist, dann wird der Standard-Kader des Bots verwendet.
        """
        await interaction.response.defer(ephemeral=True)
        if bool(clear):
            if clear.lower() not in ("y", "j", "yes", "ja", "t", "true", "1", "on"):
                await interaction.followup.send("Abbruch.", ephemeral=True)
                return
            await setPlayingCadre({})
            await interaction.followup.send(
                "Der bisher ausgewählte Spielekader wurde gelöscht. Wenn gespielt wird, wird der Standardkader benutzt.",
                ephemeral=True
            )
            return

        squadDict = await self.getNewCadre(interaction)

        await setPlayingCadre(squadDict)

        embed = Embed(
            title="Der Kader sieht wie folgt aus.", color=Colour.from_rgb(192, 192, 192)
        )
        value = ""
        for role, num in squadDict.items():
            value += f"{str(role).title()}: {num}\n"

        embed.add_field(name=f"{await self.cadreLength()}er Kader", value=value)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @cadre_group.command(name="fill", description="Fügt dem aktuellen Spielekader einen Dorfbewohner hinzu.")
    @is_gamemaster()
    async def addCitizen(self, interaction: discord.Interaction):
        """
        Zu dem aktuellen Spielekader wird ein Dorfbewohner hinzugefügt.
        Wenn es noch keinen Spielekader gibt, dann wird zu dem Standartkader ein Dorfbewohner hinzugefügt.
        Der Standartkader wird dann zum Spielekader.
        """
        await interaction.response.defer(ephemeral=True)
        cadre = await getCadre()
        if "dorfbewohner" not in cadre:
            cadre["dorfbewohner"] = 1
        else:
            cadre["dorfbewohner"] += 1
        await setPlayingCadre(cadre)
        await self.returnCadre(interaction)

    @cadre_group.command(name="minus", description="Entfernt einen Dorfbewohner aus dem aktuellen Kader.")
    @is_gamemaster()
    async def removeCitizen(self, interaction: discord.Interaction):
        """
        Von dem aktuellen Kader wird ein Dorfbewohner entfernt.
        Wenn es noch keinen Spielekader gibt, dann wird zu dem Standartkader ein Dorfbewohner entfernt.
        Der Standartkader wird dann zum Spielekader.
        Wenn es keine Dorfbewohner mehr gibt, dann passiert nichts.
        """
        await interaction.response.defer(ephemeral=True)
        cadre = await getCadre()
        if "dorfbewohner" in cadre:
            cadre["dorfbewohner"] -= 1
            if cadre["dorfbewohner"] == 0:
                del cadre["dorfbewohner"]
                await interaction.followup.send(
                    "Jetzt gibt es keine Dorfbewohner mehr im aktuellen Kader!",
                    ephemeral=True
                )
                await setPlayingCadre(cadre)
                return
        else:
            await interaction.followup.send(
                "Es gibt keine Dorfbewohner mehr im aktuellen Kader!",
                ephemeral=True
            )
            return
            
        await setPlayingCadre(cadre)
        await self.returnCadre(interaction)

    @cadre_group.command(name="list", description="Gibt den aktuellen Kader zurück.")
    async def returnCadre(self, interaction: discord.Interaction):
        """
        Gibt den aktuellen Kader zurück.
        """
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
            
        cadre = await getCadre()
        embed = Embed(
            title="Der Kader sieht wie folgt aus.", color=Colour.from_rgb(192, 192, 192)
        )
        value = ""
        for role, num in cadre.items():
            value += f"{str(role).title()}: {num}\n"

        embed.add_field(name=f"{await self.cadreLength()}er Kader", value=value)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="set_role", description="Gibt einem Spieler eine Rolle.")
    @app_commands.describe(player="Der Spieler", role="Die Rolle")
    @is_gamemaster()
    async def setPlayerRole(self, interaction: discord.Interaction, player: Member, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
            
        await player.add_roles(role)
        await interaction.followup.send(
            embed=Embed(
                title="Rollen des Spielers",
                description=f"Der Spieler {player.display_name} hat folgende Rollen:",
                color=Colour.random(),
            ).add_field(
                name="rollen", value="\n".join(map(lambda x: x.name, player.roles))
            ),
            ephemeral=True
        )

    @app_commands.command(name="delete", description="Löscht die angegebene Anzahl an Nachrichten.")
    @app_commands.describe(number="Die Anzahl der Nachrichten", channel="Der Kanal")
    @is_gamemaster()
    async def deleteMessages(self, interaction: discord.Interaction, number: Optional[int] = 1, channel: Optional[TextChannel] = None):
        """
        Löscht die angegebene Anzahl an Nachrichten im angegebenen Kanal.
        """
        await interaction.response.defer(ephemeral=True)

        if channel is None:
            channel = interaction.channel
            
        async for message in channel.history(limit=number, oldest_first=False):
            await message.delete()

        await interaction.followup.send(
            embed=Embed(
                title="Gelöschte Nachrichten", colour=Colour.teal()
            ).add_field(name="anzahl", value=str(number)),
            ephemeral=True
        )

    @app_commands.command(name="clear", description="Räumt die Kanäle, in denen gespielt wird, auf.")
    @is_gamemaster()
    async def clearGameChannels(self, interaction: discord.Interaction):
        """
        Die Kanäle, in denen gespielt wird, werden aufgeräumt.
        Alle Nachrichten in den Kanälen unterhalb der Kategorie Morbach werden geleert.
        Ausgenommen sind die Bot-Kanäle
        """
        await interaction.response.defer(ephemeral=True)
        
        game_category = interaction.guild.get_channel(await getChannelID("game_category"))
        bot_channels = tuple(
            interaction.guild.get_channel(await getChannelID(x))
            for x in ("bot_channel", "music_channel")
        )
        numMsgs = 0

        await interaction.followup.send("Die Nachrichten werden gelöscht.\nDies kann einen Moment dauern.", ephemeral=True)

        for category in filter(
                lambda c: c.position >= game_category.position, interaction.guild.categories
        ):
            for channel in filter(
                    lambda c: type(c) == TextChannel and c not in bot_channels,
                    category.channels,
            ):
                while history := await channel.history(oldest_first=True, limit=50).flatten():
                    for message in history:
                        await message.delete()
                        numMsgs += 1
        loveChannel = interaction.guild.get_channel(await getChannelID("lovebirds"))
        removed_players = []
        for member in filter(
                lambda player: type(player) == Member and player != interaction.guild.owner,
                loveChannel.overwrites,
        ):
            await loveChannel.set_permissions(member, overwrite=None)
            removed_players.append(member.display_name)

        embed = Embed(
            title="Gelöschte Nachrichten",
            description="Die Kanäle wurden geleert.",
            colour=Colour.teal())
        embed.add_field(name="anzahl", value=str(numMsgs))
        if removed_players:
            embed.add_field(name="liebespaar", value="\n".join(removed_players))
            
        await interaction.followup.send(embed=embed, ephemeral=True)

    @staticmethod
    async def delEmojis(EmojiList: list[Emoji]):
        for emoji in EmojiList:
            await emoji.delete()

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("settings")


async def setup(bot):
    await bot.add_cog(Settings(bot))
