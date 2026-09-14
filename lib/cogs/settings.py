from typing import Optional

import discord
from discord import Colour, Embed, Member, app_commands
from discord.channel import TextChannel
from discord.ext.commands import Cog
from discord.utils import get

from lib.bot import My_Bot
from lib.db.cadre_db import getCadre, setDefaultCadre, setPlayingCadre
from lib.db.db import getChannelID
from lib.helper.checks import is_gamemaster


class SurveyView(discord.ui.View):
    def __init__(
        self, interaction: discord.Interaction, theme: str, content: list[tuple]
    ):
        super().__init__(timeout=300)
        self.interaction = interaction
        self.result = None

        options = []
        for i, (name, value) in enumerate(content):
            val_str = str(value) if str(value).isdigit() else str(i + 1)
            options.append(
                discord.SelectOption(
                    label=name[:100], description=str(value)[:100], value=val_str
                )
            )

        self.select = discord.ui.Select(placeholder=theme[:100], options=options[:25])

        async def select_callback(i: discord.Interaction):
            self.result = int(self.select.values[0])
            await i.response.defer()
            self.stop()

        self.select.callback = select_callback
        self.add_item(self.select)


async def takeSurvey(
    interaction: discord.Interaction, theme: str, content: list[tuple]
):
    view = SurveyView(interaction, theme, content)

    if interaction.response.is_done():
        await interaction.followup.send(
            content=f"**{theme}**", view=view, wait=True, ephemeral=True
        )
    else:
        await interaction.response.send_message(
            content=f"**{theme}**", view=view, ephemeral=True
        )
        await interaction.original_response()

    await view.wait()
    await interaction.edit_original_response(view=None)
    return view.result


class Settings(Cog):
    def __init__(self, bot: My_Bot):
        self.bot = bot

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
        cadreSize = await takeSurvey(
            interaction, "Welche Kadergröße hättest du gerne", content
        )

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
        cadreNum = await takeSurvey(
            interaction, "Welchen der Kader willst du haben?", content
        )

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

    @cadre_group.command(
        name="standardkader", description="Legt den Standard-Kader fest."
    )
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
    async def changeCadre(
        self, interaction: discord.Interaction, clear: Optional[str] = None
    ):
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
                ephemeral=True,
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

    @cadre_group.command(
        name="fill",
        description="Fügt dem aktuellen Spielekader einen Dorfbewohner hinzu.",
    )
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

    @cadre_group.command(
        name="minus", description="Entfernt einen Dorfbewohner aus dem aktuellen Kader."
    )
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
                    ephemeral=True,
                )
                await setPlayingCadre(cadre)
                return
        else:
            await interaction.followup.send(
                "Es gibt keine Dorfbewohner mehr im aktuellen Kader!", ephemeral=True
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
    async def setPlayerRole(
        self, interaction: discord.Interaction, player: Member, role: discord.Role
    ):
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
            ephemeral=True,
        )

    @app_commands.command(
        name="delete", description="Löscht die angegebene Anzahl an Nachrichten."
    )
    @app_commands.describe(number="Die Anzahl der Nachrichten", channel="Der Kanal")
    @is_gamemaster()
    async def deleteMessages(
        self,
        interaction: discord.Interaction,
        number: Optional[int] = 1,
        channel: Optional[TextChannel] = None,
    ):
        """
        Löscht die angegebene Anzahl an Nachrichten im angegebenen Kanal.
        """
        await interaction.response.defer(ephemeral=True)

        if channel is None:
            channel = interaction.channel

        async for message in channel.history(limit=number, oldest_first=False):
            await message.delete()

        await interaction.followup.send(
            embed=Embed(title="Gelöschte Nachrichten", colour=Colour.teal()).add_field(
                name="anzahl", value=str(number)
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="clear", description="Räumt die Kanäle, in denen gespielt wird, auf."
    )
    @is_gamemaster()
    async def clearGameChannels(self, interaction: discord.Interaction):
        """
        Die Kanäle, in denen gespielt wird, werden aufgeräumt.
        Alle Nachrichten in den Kanälen unterhalb der Kategorie Morbach werden geleert.
        Ausgenommen sind die Bot-Kanäle
        """
        await interaction.response.defer(ephemeral=True)

        game_category = interaction.guild.get_channel(
            await getChannelID("game_category")
        )
        bot_channels = tuple(
            interaction.guild.get_channel(await getChannelID(x))
            for x in ("bot_channel", "music_channel")
        )
        numMsgs = 0

        await interaction.followup.send(
            "Die Nachrichten werden gelöscht.\nDies kann einen Moment dauern.",
            ephemeral=True,
        )

        for category in filter(
            lambda c: c.position >= game_category.position, interaction.guild.categories
        ):
            for channel in filter(
                lambda c: isinstance(c, TextChannel) and c not in bot_channels,
                category.channels,
            ):
                while history := await channel.history(
                    oldest_first=True, limit=50
                ).flatten():
                    for message in history:
                        await message.delete()
                        numMsgs += 1
        loveChannel = interaction.guild.get_channel(await getChannelID("lovebirds"))
        removed_players = []
        for member in filter(
            lambda player: (
                isinstance(player, Member) and player != interaction.guild.owner
            ),
            loveChannel.overwrites,
        ):
            await loveChannel.set_permissions(member, overwrite=None)
            removed_players.append(member.display_name)

        embed = Embed(
            title="Gelöschte Nachrichten",
            description="Die Kanäle wurden geleert.",
            colour=Colour.teal(),
        )
        embed.add_field(name="anzahl", value=str(numMsgs))
        if removed_players:
            embed.add_field(name="liebespaar", value="\n".join(removed_players))

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Settings(bot))
