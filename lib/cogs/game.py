import asyncio
import random
from datetime import date, datetime, timedelta
from typing import Optional, Union, cast

import discord
from apscheduler.triggers.date import DateTrigger
from babel.dates import format_date
from discord import Colour, Embed, Guild, Member, Role, VoiceChannel, Interaction, SelectOption
from discord.abc import Snowflake
from discord.ext import commands
from discord.ext.commands import Cog, Context, check, CheckFailure
from discord.ext.commands.core import has_role
from discord.ui import View, Item, Select
from numpy.random import randint

from lib.bot import My_Bot
from lib.cogs.help import is_guild_owner
from lib.helper.converters import MyRoleConverter
from lib.helper.checks import is_gamemaster
from lib.cogs.settings import takeSurvey
from lib.db.db import getChannelID, getElo, getRoleID, getRoleTeam, saveCurrentGame
from lib.helper.constants import CHRONICLE_PATTERN
from lib.helper.errors import InputError
from lib.db.cadre_db import getCadre, getCurrentGameCadre, setCurrentGameCadre


class Game(Cog):
    """
    Das Modul, welches die Funktionen zum Spielen hinzufügt.
    """

    _choices_active = False

    def __init__(self, bot: My_Bot):
        self.bot = bot
        self._choices: dict[Member, str] = {}

    @classmethod
    def _enable(cls):
        cls._choices_active = True

    @classmethod
    def _disable(cls):
        cls._choices_active = False

    async def cadreLength(self) -> int:
        cadre = await getCadre()
        length = 0
        for num in cadre.values():
            length += num
        return length

    @staticmethod
    async def getSquad(players: list[Member]) -> dict[Member, str]:
        returnDict = {}
        length = len(players)
        for player in players:
            rand = randint(length)
            while rand in returnDict.values():
                rand = randint(length)
            returnDict[player] = rand
        cadreList = []
        for role, count in (await getCadre()).items():
            role = role.lower().strip()
            if role in ("dorfbewohner", "werwolf", "geschwister"):
                for num in range(1, count + 1):
                    cadreList.append(f"{role}-{num}".replace(" ", "-"))
            else:
                for num in range(count):
                    cadreList.append(role)
        currentCadre = {}
        for key, value in returnDict.items():
            returnDict[key] = cadreList[value]
            currentCadre[str(key.id)] = {
                "role": cadreList[value],
                "dead": False,
                "lovebirds": False,
            }
        await setCurrentGameCadre(currentCadre)
        return returnDict

    @staticmethod
    async def getSquadWithChoices(players: list[Member], choices: dict[Member, str]) -> dict[Member, str]:
        # Temporarily bypassing choice logic until fully migrated to async SQLAlchemy
        return await Game.getSquad(players)

    @staticmethod
    async def checkRolePos(role: Role, guild: Guild):
        dead_id = await getRoleID("dead")
        dead_role = guild.get_role(dead_id)
        if dead_role and role.position >= dead_role.position:
            return True
        return False

    @commands.hybrid_command(name="start", aliases=["go", "starten"])
    @is_gamemaster()
    async def startGame(self, ctx: Context):
        """
        Die Funktion startet das Spiel.
        Gestartet wird mit dem bisher ausgewählten Kader und den Spielern,
         die mit dem Spielleiter (Autor) in einem Sprachkanal sind.
        Es setzt außerdem den Kader und den Spielleiter für die Chronik.
        """
        if ctx.author.voice is None:
            await ctx.send(
                "Bitte verbinde dich mit einem Sprachkanal und versuche es dann erneut.",
                delete_after=30.0,
            )
            return

        playerList = []
        numGamemaster = 0

        gm_role_id = await getRoleID("gamemaster")
        for member in ctx.author.voice.channel.members:
            if any(gm_role_id == role.id for role in member.roles):
                numGamemaster += 1
                if numGamemaster > 1:
                    await ctx.send(
                        "Ihr habt mehr als einen Spielleiter im Kanal. Bitte entferne die Rollen, damit nur ein "
                        "Spielleiter im Kanal ist",
                        delete_after=30.0,
                    )
                    return
            elif member.bot:
                continue
            else:
                playerList.append(member)

        if len(playerList) < await self.cadreLength():
            embed = Embed(
                title="Kein Spielstart möglich",
                description="Für ein Spiel benötigt ihr noch mehr Spieler in dem Kanal.",
                colour=Colour.from_rgb(255, 0, 0),
            )
            embed.add_field(
                name="Anzahl fehlender Spieler",
                value=f"{await self.cadreLength() - len(playerList)}",
            )
            embed.add_field(
                name="Mögliche Lösungen",
                value="Ihr könntet mehr Spieler in den Sprachkanal holen oder die Kader-Größe runterstellen.",
            )
            await ctx.send(embed=embed, delete_after=30.0)
            return

        elif len(playerList) > await self.cadreLength():
            embed = Embed(
                title="Kein Spielstart möglich",
                description="Für ein Spiel habt ihr zu viele Spieler in dem Kanal.",
                colour=Colour.from_rgb(255, 0, 0),
            )
            embed.add_field(
                name="Anzahl überzähliger Spieler",
                value=f"{len(playerList) - await self.cadreLength()}",
            )
            embed.add_field(
                name="Mögliche Lösungen",
                value="Ihr könntet Spieler aus dem Sprachkanal entfernen oder die Kader-Größe erhöhen.",
            )
            await ctx.send(embed=embed, delete_after=30.0)
            return

        else:
            await ctx.send(
                "Es sind genug Spieler da. Wir beginnen mit der Rollenverteilung.",
                delete_after=60.0,
            )
            squad = self.getSquad(playerList)
            embed = Embed(
                title="Kaderaufstellung", colour=Colour.from_rgb(192, 192, 192), type="article"
            )

            fields = []
            for player, gamerole in squad.items():
                fields.append((gamerole, player.display_name, False))

            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)
            await ctx.send(embed=embed)
            GVoiceChannel = self.bot.get_channel(await getChannelID("GameVoiceChannel"))
            for player, gamerole in squad.items():
                for role in player.roles:
                    if await self.checkRolePos(role, ctx.guild):
                        await player.remove_roles(role)
                await player.add_roles(ctx.guild.get_role(await getRoleID(gamerole)))
                await player.move_to(cast(VoiceChannel, GVoiceChannel))
            await ctx.author.move_to(cast(VoiceChannel, GVoiceChannel))
            await ctx.send(
                "Alle Spieler sind im Sprachkanal und das Spiel kann beginnen",
                delete_after=60.0,
            )
            self.bot.emitter.emit("newGame")
            self.bot._current_gamemaster = ctx.author

    @commands.hybrid_command(name="start_with_choice", aliases=["rollenwahl", "rolechoice"])
    @is_gamemaster()
    async def startGameWithChoice(self, ctx: Context):
        """
        Diese Funktion startet ein Spiel mit Rollenwahl.
        Die Spieler haben 5 Minuten Zeit sich mithilfe des Slashcommands `choose` eine Rolle oder eine Fraktion aus dem eingestellten Kader auszuwählen.
        Gestartet wird mit dem bisher ausgewählten Kader und den Spielern, die mit dem Spielleiter (Autor) in einem Sprachkanal sind.
        Es setzt außerdem den Kader und den Spielleiter für die Chronik.
        """
        if ctx.author.voice is None:
            await ctx.send(
                "Bitte verbinde dich mit einem Sprachkanal und versuche es dann erneut.",
                delete_after=30.0,
            )
            return

        playerList = []
        numGamemaster = 0

        gm_role_id = await getRoleID("gamemaster")
        for member in ctx.author.voice.channel.members:
            if any(gm_role_id == role.id for role in member.roles):
                numGamemaster += 1
                if numGamemaster > 2:
                    await ctx.send(
                        "Ihr habt mehr als einen Spielleiter im Kanal. Bitte entferne die Rollen, damit nur ein Spielleiter im Kanal ist",
                        delete_after=30.0,
                    )
                    return
            elif member.bot:
                continue
            else:
                playerList.append(member)

        if len(playerList) < await self.cadreLength():
            embed = Embed(
                title="Kein Spielstart möglich",
                description="Für ein Spiel benötigt ihr noch mehr Spieler in dem Kanal.",
                colour=Colour.from_rgb(255, 0, 0),
            )
            embed.add_field(
                name="Anzahl fehlender Spieler",
                value=f"{await self.cadreLength() - len(playerList)}",
            )
            embed.add_field(
                name="Mögliche Lösungen",
                value="Ihr könntet mehr Spieler in den Sprachkanal holen oder die Kader-Größe runterstellen.",
            )
            await ctx.send(embed=embed, delete_after=30.0)
            return

        elif len(playerList) > await self.cadreLength():
            embed = Embed(
                title="Kein Spielstart möglich",
                description="Für ein Spiel habt ihr zu viele Spieler in dem Kanal.",
                colour=Colour.from_rgb(255, 0, 0),
            )
            embed.add_field(
                name="Anzahl überzähliger Spieler",
                value=f"{len(playerList) - await self.cadreLength()}",
            )
            embed.add_field(
                name="Mögliche Lösungen",
                value="Ihr könntet Spieler aus dem Sprachkanal entfernen oder die Kader-Größe erhöhen.",
            )
            await ctx.send(embed=embed, delete_after=30.0)
            return

        else:
            await ctx.send(
                "Es sind genug Spieler da. Wir beginnen mit der Rollenverteilung.",
                delete_after=60.0,
            )
            await self.bot.get_channel(await getChannelID("game_text_channel")).send("Es können nun alle für 5 Minuten lang mithilfe des Slash-Befehls `/choose` sich eine Fraktion oder eine Rolle "
                                                                               "aussuchen", delete_after=5 * 60)
            Game._enable()
            await asyncio.create_task(asyncio.sleep(60 * 5))
            Game._disable()
            squad = await self.getSquadWithChoices(playerList, self._choices)
            embed = Embed(
                title="Kaderaufstellung", colour=Colour.from_rgb(192, 192, 192), type="article"
            )

            fields = []
            for player, gamerole in squad.items():
                fields.append((gamerole, player.display_name, False))

            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)
            await ctx.send(embed=embed)
            GVoiceChannel = self.bot.get_channel(await getChannelID("GameVoiceChannel"))
            for player, gamerole in squad.items():
                for role in player.roles:
                    if await self.checkRolePos(role, ctx.guild):
                        await player.remove_roles(role)
                await player.add_roles(ctx.guild.get_role(await getRoleID(gamerole)))
                await player.move_to(cast(VoiceChannel, GVoiceChannel))
            await ctx.author.move_to(cast(VoiceChannel, GVoiceChannel))
            await ctx.send(
                "Alle Spieler sind im Sprachkanal und das Spiel kann beginnen",
                delete_after=60.0,
            )
            self.bot.emitter.emit("newGame")
            self.bot._current_gamemaster = ctx.author
            self._choices = {}

    @commands.hybrid_command(name="choose", description="Befehl, um die Rolle oder Fraktion zu wählen, die man bei dem Modus Rollenwahl bekommen will.")
    @check(lambda x: Game._choices_active)
    async def setChoices(self, ctx: Context):
        cadre = await getCadre()
        selection = RoleSelection(list(cadre.keys()))
        await ctx.send("Wähle eine Rolle aus", view=selection, delete_after=60.0, ephemeral=True)
        try:
            await self.bot.wait_for("interaction", timeout=60.0)
            if selection.selected is None:
                await selection.interaction.response.send_message(
                    "Deine Wahl ist leider in diesem Kader nicht verfügbar. Versuch es mit einer anderen Wahl erneut. Bei großen Problemen, wende dich bitte an den Spielleiter oder den Entwickler",
                    ephemeral=True)
            elif selection.selected == "None":
                await selection.interaction.response.send_message(
                    f"Deine bisherige Auswahl ({self._choices[ctx.author] if self._choices.get(ctx.author) is not None else 'Keine Auswahl'}) wurde nicht geändert", ephemeral=True)
            else:
                self._choices[ctx.author] = selection.selected
                await selection.interaction.response.send_message(f"Deine Auswahl wurde aus '{self._choices[ctx.author]}' festgelegt.", ephemeral=True)
        except TimeoutError:
            pass

    @setChoices.error
    async def setChoiceError(self, ctx: Context, exc: Exception):
        if isinstance(exc, CheckFailure):
            await ctx.send("Du kannst keine Rolle auswählen. Entweder sind die 5 Minuten schon vorbei oder es wurde noch kein Spiel mit Rollenwahl gestartet.", delete_after=30, ephemeral=True)
        else:
            raise exc

    @commands.hybrid_command(name="dead", aliases=["tot"])
    @is_gamemaster()
    async def setDead(self, ctx: Context, player: Optional[Member]):
        """
        Der gegebene Spieler wird 'getötet'.
        Seine Rollen werden entfernt und ihm wird die Rolle 'tot' gegeben.
        Für die Chronik wird der Spieler auf 'tot' gesetzt.
        ``player``: Der zu tötende Spieler (optional)
        """
        gameCadre = await getCurrentGameCadre()
        if player is None:
            livingPlayers: list[tuple] = [(x[0], list(gameCadre.keys()).index(x[0])) for x in gameCadre.items() if not x[1]["dead"]]
            playerNum = await takeSurvey(
                ctx, "Welchen Spieler willst du auf tot stellen?", livingPlayers
            )
            player = livingPlayers[playerNum]
        for role in player.roles:
            if await self.checkRolePos(role, ctx.guild) and role.id != 768494431136645127:
                await player.remove_roles(role)
                await player.edit(mute=True)
        await player.add_roles(ctx.guild.get_role(await getRoleID("dead")))
        # Der zwischengespeicherte Spielekader wird akktualisiert
        gameCadre[player]["dead"] = True
        await setCurrentGameCadre(gameCadre)
        # Der Nickname des Spielers wird geändert
        nick = player.display_name
        await player.edit(nick=f"♰ {nick}")
        # Die Nachricht des erfolgreichen Tötens wird gesendet
        embed = Embed(
            title="Erfolgreich getötet!",
            description=f"Der Spieler {player.name} wurde getötet.",
            colour=Colour.from_rgb(0, 0, 0),
        )
        embed.add_field(
            name="rollen", value="\n".join(role.name for role in player.roles)
        )
        await ctx.send(embed=embed, delete_after=60.0)

    @commands.hybrid_command(name="captain", aliases=["hauptmann", "cp"])
    @is_gamemaster()
    async def setCaptain(self, ctx: Context, player: Optional[Member]):
        """
        Der gegebene Spieler wird die Rolle 'Hauptmann' gegeben.
        Für die Chronik wird der Spieler zum 'Hauptmann' gemacht.
        ``player``: Der Spieler, der zum Hauptmann wird (optional)
        """
        gameCadre = await getCurrentGameCadre()
        if player is None:
            livingPlayers: list[tuple] = [(x[0], list(gameCadre.keys()).index(x[0])) for x in gameCadre.items() if not x[1]["dead"]]
            playerNum = await takeSurvey(
                ctx, "Welchen Spieler willst du zum Hauptmann machen?", livingPlayers
            )
            player = livingPlayers[playerNum]
        await player.add_roles(ctx.guild.get_role(await getRoleID("captain")))
        gameCadre[player]["captain"] = True
        await setCurrentGameCadre(gameCadre)
        embed = Embed(
            title="Erfolgreich zum Hauptmann befördert!",
            description=f"Der Spieler {player.display_name} wurde zum Hauptmann ernannt.",
            colour=Colour.orange(),
        )
        embed.add_field(
            name="rollen", value="\n".join(role.name for role in player.roles)
        )
        await ctx.send(embed=embed, delete_after=60.0)

    @commands.hybrid_command(name="chronicle", aliases=["chronik", "writeChronicle", "wrCr"])
    @is_gamemaster()
    async def writeChronicle(self, ctx: Context, max_players: Optional[int] = 20):
        """
        Die Chronik für dieses Spiel wird in den zugehörigen Kanal geschrieben.
        Es kann nur von dem letzten Spiel die Chronik geschrieben werden.
        Die Chronik kann nur richtig geschrieben werden, wenn der Bot durch die Befehle 'tot', 'hauptmann' und 'start' alle Informationen richtig bekommen hat.
        ``max_players``: Die maximale Spielerzahl (optional) (default = 20)
        """
        gameCadre = await getCurrentGameCadre()
        if gameCadre == {}:
            await ctx.send(
                embed=Embed(
                    title="Spielfehler!",
                    description="Ihr müsst zuerst ein Spiel spielen!",
                    colour=Colour.from_rgb(255, 0, 0),
                ),
                delete_after=60.0,
            )
            raise InputError(
                "Der Spielleiter hat kein Spiel gestartet oder vergessen alles einzutragen"
            )
        resultCadre = {}
        for player, attr in gameCadre.items():
            value = attr["role"]
            value += " [tot]" if attr["dead"] else ""
            value += " (Hauptmann)" if attr["captain"] and not attr["dead"] else ""
            value += " (verliebt)" if attr["lovebirds"] else ""
            value += (
                f" ({await getElo(player.id)})" if await getElo(player.id) is not None else " (No Elo)"
            )
            resultCadre[player.display_name] = value
        winner = "Niemand"
        if any(lovebirds := dict(n for n in gameCadre.items() if n[1]["lovebirds"])):
            teams = [await getRoleTeam(value["role"]) for value in lovebirds.values()]
            if not teams.count("2") and all(not bird["dead"] for bird in lovebirds):
                winner = "Liebespaar"
        elif winner == "Niemand":
            livingTeams = set()
            for value in gameCadre.values():
                role, dead, captain, lovebirds = value.values()
                if not dead and not lovebirds:
                    livingTeams.add(await getRoleTeam(role))
                elif not dead and lovebirds:
                    livingTeams.add("Liebespaar")
            if "Jason" in livingTeams:
                winner = "Jason"
            elif (
                    "Werschweinchen" in livingTeams
                    and "Werwölfe" not in livingTeams
                    or "Weißer Werwolf" not in livingTeams
            ):
                winner = "Werschweinchen"
            elif len(livingTeams) == 1:
                winner = str(livingTeams)
            else:
                await ctx.send(
                    "Es kann kein Gewinner ermittelt werden. Stelle alle, die verloren haben bitte auf 'tot' und "
                    "versuch es erneut "
                )
                return
        if date.today() == self.bot._lastRound:
            self.bot._roundNum += 1
        else:
            self.bot._roundNum = 1
        msg = CHRONICLE_PATTERN.format(
            datum=format_date(date.today(), "EEEE, dd.MM.yyyy", locale="de_DE"),
            numRound=self.bot._roundNum,
            maxPlayer=max_players,
            numPlayer=len(gameCadre),
            gamemaster=self.bot._current_gamemaster.mention,
            playerDict="\n".join(map(lambda x: f"{x[0].removeprefix('♰')}: {x[1]}", resultCadre.items())),
            lovebird=",".join(
                map(
                    lambda m: m[0].display_name.removeprefix('♰'),
                    filter(lambda x: x[1]["lovebirds"], gameCadre.items()),
                )
            )
            if any(filter(lambda x: x[1]["lovebirds"], gameCadre.items()))
            else "Nein",
            winner=winner,
        )
        await ctx.guild.get_channel(await getChannelID("chronicle")).send(msg)
        gameNumber = await saveCurrentGame(gameCadre, winner)
        self.bot.emitter.emit("calcElo", gameNumber)
        self.bot._current_gamemaster = None
        self.bot._lastRound = date.today()
        self.bot._ghostvoices = False
        await ctx.invoke(self.removeLovebirds)
        gm_role_id = await getRoleID("gamemaster")
        for player in gameCadre:
            nick: str = player.display_name
            await player.edit(nick=nick.removeprefix("♰"))
            for role in player.roles:
                if await self.checkRolePos(role, ctx.guild) and role.id != gm_role_id:
                    await player.remove_roles(role)
            if player.voice is not None:
                await player.edit(mute=False)
        await setCurrentGameCadre({})

    @commands.hybrid_command(name="love", aliases=["liebe", "liebende"])
    @is_gamemaster()
    async def setLovebirds(self, ctx: Context, player1: Member, player2: Member):
        """
        Die beiden gegebenen Spieler werden das Liebespaar.
        Sie bekommen Zugang zum Liebespaar-Kanal.
        ``player1``: Der eine Spieler des Liebespaars
        ``player2``: Der andere Spieler des Liebespaars
        """
        loveChannel = ctx.guild.get_channel(await getChannelID("lovebirds"))
        gameCadre = await getCurrentGameCadre()
        await loveChannel.set_permissions(
            player1, send_messages=True, read_messages=True, read_message_history=True
        )
        await loveChannel.set_permissions(
            player2, send_messages=True, read_messages=True, read_message_history=True
        )
        gameCadre[player1]["lovebirds"] = True
        gameCadre[player2]["lovebirds"] = True
        await setCurrentGameCadre(gameCadre)
        await ctx.send(
            embed=Embed(
                title="Liebespaar",
                description="Das Liebespaar wurde gesetzt",
                colour=Colour.from_rgb(252, 15, 192),
            ).add_field(
                name="Spieler:", value=f"{player1.display_name}\n{player2.display_name}"
            ),
            delete_after=60.0,
        )

    @commands.hybrid_command(name="remove_love", aliases=["minusLove", "entferneLiebe", "rmLv"])
    @is_gamemaster()
    async def removeLovebirds(self, ctx: Context):
        """
        Das Liebespaar wird aufgelöst.
        Der Zugang zum Liebespaar-Kanal wird für die Beiden wieder entfernt.
        """
        loveChannel = ctx.guild.get_channel(await getChannelID("lovebirds"))
        gameCadre = await getCurrentGameCadre()
        removedPlayer = []
        for member in filter(
                lambda memb: type(memb) == Member and memb != ctx.guild.owner,
                loveChannel.overwrites,
        ):
            await loveChannel.set_permissions(member, overwrite=None)
            gameCadre[member]["lovebirds"] = False
            removedPlayer.append(member.display_name)
        await ctx.send(
            embed=Embed(
                title="Liebespaar",
                description="Das Liebespaar wurde entfernt",
                colour=Colour.from_rgb(255, 0, 120),
            ).add_field(name="Spieler:", value="\n".join(removedPlayer)),
            delete_after=60.0,
        )

    @commands.hybrid_command(name="ghostvoices", aliases=["geisterstimmen", "gv", "gs"])
    @is_gamemaster()
    async def setGhostvoices(self, ctx: Context):
        """
        Schaltet die Geiterstimmen frei.
        Werden nach 5 Minuten automatisch wieder gesperrt.
        """
        self.bot._ghostvoices = True
        del_time = datetime.now() + timedelta(minutes=5.0)
        self.bot.scheduler.add_job(
            self.resetGhostvoices(), DateTrigger(del_time, del_time.tzinfo)
        )

    @commands.hybrid_command(name="reset", aliases=["resette", "restart"])
    @is_gamemaster()
    async def resetRole(self, ctx: Context, player: Optional[Member] = None, reset_all: bool = False):
        """
        Setzt den Spieler zum Stand am Anfang der Runde zurück.
        ``player``: Der Spieler, dessen Rolle zurückgesetzt werden soll
        ``reset_all``: True, um das gesamte Spiel zurückzusetzen
        """
        if not player and not reset_all:
            await ctx.send("Gibt bitte einen Spieler ein um diesen zurückzusetzen oder wähle reset_all=True.", delete_after=20.0)
            return
            
        cadre = await getCurrentGameCadre()
        res_cadre = cadre.copy()
        
        if reset_all:
            title = "Das Spiel wurde zurückgesetzt"
            for ply, attrs in cadre.items():
                for attr, value in attrs.items():
                    if type(value) == bool:
                        res_cadre[ply][attr] = False
                for role in ply.roles:
                    if await self.checkRolePos(role, ctx.guild):
                        await ply.remove_roles(role)
                await ply.add_roles(ctx.guild.get_role(await getRoleID(attrs["role"])))
        else:
            if player not in cadre:
                await ctx.send("Dieser Spieler ist nicht im aktuellen Spielkader.", delete_after=20.0)
                return
            title = "Der Spieler wurde zurückgesetzt"
            for attr, value in cadre[player].items():
                if type(value) == bool:
                    res_cadre[player][attr] = False
            for role in player.roles:
                if await self.checkRolePos(role, ctx.guild):
                    await player.remove_roles(role)
                await player.add_roles(ctx.guild.get_role(await getRoleID(cadre[player]["role"])))
                
        await setCurrentGameCadre(res_cadre)
        embed = Embed(title=title,
                      description="Das Spiel sieht jetzt wie folgt aus:",
                      color=Colour.from_rgb(255, 0, 120))
        value = "\n".join(map(lambda m: f"{m[0].display_name}: {m[1]['role'].upper()}", res_cadre.items()))
        embed.add_field(name="kader", value=value)
        await ctx.send(embed=embed, delete_after=60.0)

    @commands.hybrid_command(name="set_gamemaster", aliases=["sG"], hidden=True)
    @check(is_guild_owner)
    async def setGamemaster(self, ctx: Context, player: Member):
        self.bot._current_gamemaster = player
        await ctx.send(f"{player.mention} ist nun Spielleiter")

    def resetGhostvoices(self):
        self.bot._ghostvoices = False

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("game")


async def setup(bot: My_Bot):
    await bot.add_cog(Game(bot))


class RoleSelection(View):
    def __init__(self, cadre_keys: list[str], *items: Item, timeout: Optional[float] = 180.0):
        super().__init__(*items, timeout=timeout)
        self.interaction: Interaction = None
        self.selected: str = None
        
        options = [SelectOption(label=x[0], description=x[1]) for x in
                 [(i.title(), "Rolle") for i in cadre_keys] + [("Dorf", "Fraktion"), ("Werwölfe", "Fraktion"), ("Drittpartei", "Fraktion")]] + \
                [SelectOption(label="Keine Auswahl", description="Abbrechen der Auswahl, indem nichts gewählt wird", value="None", default=True)]
                
        self.select_menu = discord.ui.Select(
            placeholder="Choose a role or fraction you want to play",
            min_values=1,
            max_values=1,
            options=options
        )
        self.select_menu.callback = self.select_callable
        self.add_item(self.select_menu)

    async def select_callable(self, interaction: Interaction):
        self.stop()
        self.selected = self.select_menu.values[0]
        self.interaction = interaction
