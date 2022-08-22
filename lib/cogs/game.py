import asyncio
import random
from datetime import date, datetime, timedelta
from typing import Optional, Union, cast

import discord
from apscheduler.triggers.date import DateTrigger
from babel.dates import format_date
from discord import Colour, Embed, Guild, Member, Role, VoiceChannel, ApplicationContext, Interaction, SelectOption, CheckFailure
from discord.abc import Snowflake
from discord.ext import commands
from discord.ext.commands import Cog, Context, check
from discord.ext.commands.core import has_role
from discord.ui import View, Item, Select
from numpy.random import randint

from lib.bot import My_Bot
from lib.cogs.help import is_guild_owner
from lib.cogs.settings import takeSurvey
from lib.db.db import getChannelID, getElo, getRoleID, getRoleTeam, saveCurrentGame, getData, cursor
from lib.helper.constants import (
    CHRONICLE_PATTERN,
    InputError,
    getCadre,
    getCurrentGameCadre,
    setCurrentGameCadre,
)


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

    @property
    def cadreLength(self) -> int:
        cadre = getCadre()
        length = 0
        for num in cadre.values():
            length += num
        return length

    @staticmethod
    def getSquad(players: list[Member]) -> dict[Member, str]:
        returnDict = {}
        length = len(players)
        for player in players:
            rand = randint(length)
            while rand in returnDict.values():
                rand = randint(length)
            returnDict[player] = rand
        cadreList = []
        for role, count in getCadre().items():
            role = role.lower().strip()
            if role in ("dorfbewohner", "werwolf", "geschwister"):
                for num in range(1, count + 1):
                    cadreList.append(f"{role}-{num}".replace(" ", "-"))
            else:
                cadreList.append(role.replace(" ", "-"))
        for member, num in returnDict.items():
            returnDict[member] = cadreList[num]
        currentCadre: [Member, dict[str, str | bool]] = {}
        for player, role in returnDict.items():
            currentCadre[player] = {
                "role": role,
                "dead": False,
                "captain": False,
                "lovebirds": False,
            }
        setCurrentGameCadre(currentCadre)
        return returnDict

    @staticmethod
    def getSquadWithChoices(players: list[Member], choices: dict[Member, str]) -> dict[Member, str]:
        res_dict: dict[Member, str] = {}

        def processChoice(value: str) -> str:
            returnValue = None
            if value in ("Werwölfe", "Dorf", "Drittpartei"):
                if value == "Werwölfe":
                    werewolfFraction = (x for x in getData("roles", ("name_bot",), ("team", "Werwölfe")) if x.strip("-0123456789 ") in getCadre().keys())
                    print(werewolfFraction)
                    try:
                        returnValue = random.choice([x for x in werewolfFraction if x not in res_dict.values()])
                    except IndexError:
                        pass
                elif value == "Dorf":
                    dorfFraction = (x for x in getData("roles", ("name_bot",), ("team", "Dorf")) if x in getCadre().keys())
                    print(dorfFraction)
                    try:
                        returnValue = random.choice([x for x in dorfFraction if x not in res_dict.values()])
                    except IndexError:
                        pass
                else:
                    thirdParty = (x for x in (getData("role", ("name_bot",), ("team", x)) for x in ("Weißer Werwolf", "Werschweinchen", "Jason")) if x in getCadre().keys())
                    print(thirdParty)
                    try:
                        returnValue = random.choice([x for x in thirdParty if x not in res_dict.values()])
                    except IndexError:
                        pass
            if returnValue is None:
                remaining_cadre = [x for x, in cursor.execute("SELECT name_bot FROM roles WHERE team IS NOT NULL").fetchall()
                                   if x.strip(" -1234567890") in getCadre().keys() and x not in res_dict.values()]
                returnValue = random.choice(remaining_cadre)
            return returnValue

        if any(True for x in choices.values() if list(choices.values()).count(x) > 1):
            duplicates = [(k, v) for k, v in choices.items() if list(choices.values()).count(v) > 1]
            singles = [(k, v) for k, v in choices.items() if list(choices.values()).count(v) == 1]
            for k, v in singles:
                res_dict[k] = processChoice(v)
            orderedDuplicates: list[list[tuple[Member, str]]] = []
            duplicates.sort(key=lambda x: x[1])
            for i, x in enumerate(duplicates):
                if x[1] == duplicates[i - 1][1]:
                    orderedDuplicates[-1].append(x)
                else:
                    orderedDuplicates.append([x])
            for duplicate in orderedDuplicates:
                if duplicate[0][1] in ("Werwölfe", "Dorf", "Drittpartei"):
                    maximumPlayersPerRole = len([x for x in getData("roles", ("name_bot",), ("team", duplicate[0][1])) if x.strip("-0123456789 ") in getCadre().keys()])
                    if len(duplicate) > maximumPlayersPerRole:
                        randomPlayers = random.choices(duplicate, k=maximumPlayersPerRole)
                        for k, v in randomPlayers:
                            res_dict[k] = processChoice(v)
                    else:
                        for k, v in duplicate:
                            res_dict[k] = processChoice(v)
                else:
                    maximumPlayersPerRole = getCadre()[duplicate[0][1]]
                    if len(duplicate) > maximumPlayersPerRole:
                        randomPlayers = random.choices(duplicate, k=maximumPlayersPerRole)
                        for k, v in randomPlayers:
                            res_dict[k] = processChoice(v)
                    else:
                        for k, v in duplicate:
                            res_dict[k] = processChoice(v)
        for m in (x for x in players if x not in res_dict.keys()):
            remainingCadre = [x for x, in cursor.execute("SELECT name_bot FROM roles WHERE team IS NOT NULL").fetchall()
                              if x.strip(" -1234567890") in getCadre().keys() and x not in res_dict.values()]
            res_dict[m] = random.choice(remainingCadre)

        currentCadre: [Member, dict[str, str | bool]] = {}
        for player, role in res_dict.items():
            currentCadre[player] = {
                "role": role,
                "dead": False,
                "captain": False,
                "lovebirds": False,
            }
        setCurrentGameCadre(currentCadre)

        return res_dict

    @staticmethod
    def checkRolePos(role: Role, guild: Guild):
        if role.position >= guild.get_role(getRoleID("dead")).position:
            return True
        return False

    @commands.command(name="start", aliases=["go", "starten"])
    @has_role(getRoleID("gamemaster"))
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

        for member in ctx.author.voice.channel.members:
            if any(getRoleID("gamemaster") == role.id for role in member.roles):
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

        if len(playerList) < self.cadreLength:
            embed = Embed(
                title="Kein Spielstart möglich",
                description="Für ein Spiel benötigt ihr noch mehr Spieler in dem Kanal.",
                colour=Colour.from_rgb(255, 0, 0),
            )
            embed.add_field(
                name="Anzahl fehlender Spieler",
                value=f"{self.cadreLength - len(playerList)}",
            )
            embed.add_field(
                name="Mögliche Lösungen",
                value="Ihr könntet mehr Spieler in den Sprachkanal holen oder die Kader-Größe runterstellen.",
            )
            await ctx.send(embed=embed, delete_after=30.0)
            return

        elif len(playerList) > self.cadreLength:
            embed = Embed(
                title="Kein Spielstart möglich",
                description="Für ein Spiel habt ihr zu viele Spieler in dem Kanal.",
                colour=Colour.from_rgb(255, 0, 0),
            )
            embed.add_field(
                name="Anzahl überzähliger Spieler",
                value=f"{len(playerList) - self.cadreLength}",
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
            GVoiceChannel = self.bot.get_channel(getChannelID("GameVoiceChannel"))
            for player, gamerole in squad.items():
                for role in player.roles:
                    if self.checkRolePos(role, ctx.guild):
                        await player.remove_roles(role)
                await player.add_roles(ctx.guild.get_role(getRoleID(gamerole)))
                await player.move_to(cast(VoiceChannel, GVoiceChannel))
            await ctx.author.move_to(cast(VoiceChannel, GVoiceChannel))
            await ctx.send(
                "Alle Spieler sind im Sprachkanal und das Spiel kann beginnen",
                delete_after=60.0,
            )
            self.bot.emitter.emit("newGame")
            self.bot._current_gamemaster = ctx.author

    @commands.command(name="startWithChoice", aliases=["rollenwahl", "rolechoice"])
    @has_role(getRoleID("gamemaster"))
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

        for member in ctx.author.voice.channel.members:
            if any(getRoleID("gamemaster") == role.id for role in member.roles):
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

        if len(playerList) < self.cadreLength:
            embed = Embed(
                title="Kein Spielstart möglich",
                description="Für ein Spiel benötigt ihr noch mehr Spieler in dem Kanal.",
                colour=Colour.from_rgb(255, 0, 0),
            )
            embed.add_field(
                name="Anzahl fehlender Spieler",
                value=f"{self.cadreLength - len(playerList)}",
            )
            embed.add_field(
                name="Mögliche Lösungen",
                value="Ihr könntet mehr Spieler in den Sprachkanal holen oder die Kader-Größe runterstellen.",
            )
            await ctx.send(embed=embed, delete_after=30.0)
            return

        elif len(playerList) > self.cadreLength:
            embed = Embed(
                title="Kein Spielstart möglich",
                description="Für ein Spiel habt ihr zu viele Spieler in dem Kanal.",
                colour=Colour.from_rgb(255, 0, 0),
            )
            embed.add_field(
                name="Anzahl überzähliger Spieler",
                value=f"{len(playerList) - self.cadreLength}",
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
            await self.bot.get_channel(getChannelID("game_text_channel")).send("Es können nun alle für 5 Minuten lang mithilfe des Slash-Befehls `/choose` sich eine Fraktion oder eine Rolle "
                                                                               "aussuchen", delete_after=5 * 60)
            Game._enable()
            await asyncio.create_task(asyncio.sleep(60 * 5))
            Game._disable()
            squad = self.getSquadWithChoices(playerList, self._choices)
            embed = Embed(
                title="Kaderaufstellung", colour=Colour.from_rgb(192, 192, 192), type="article"
            )

            fields = []
            for player, gamerole in squad.items():
                fields.append((gamerole, player.display_name, False))

            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)
            await ctx.send(embed=embed)
            GVoiceChannel = self.bot.get_channel(getChannelID("GameVoiceChannel"))
            for player, gamerole in squad.items():
                for role in player.roles:
                    if self.checkRolePos(role, ctx.guild):
                        await player.remove_roles(role)
                await player.add_roles(ctx.guild.get_role(getRoleID(gamerole)))
                await player.move_to(cast(VoiceChannel, GVoiceChannel))
            await ctx.author.move_to(cast(VoiceChannel, GVoiceChannel))
            await ctx.send(
                "Alle Spieler sind im Sprachkanal und das Spiel kann beginnen",
                delete_after=60.0,
            )
            self.bot.emitter.emit("newGame")
            self.bot._current_gamemaster = ctx.author
            self._choices = {}

    @discord.slash_command(name="choose", description="Befehl, um die Rolle oder Fraktion zu wählen, die man bei dem Modus Rollenwahl bekommen will.")
    @check(lambda x: Game._choices_active)
    async def setChoices(self, ctx: ApplicationContext):
        selection = RoleSelection()
        await ctx.respond("Wähle eine Rolle aus", view=selection, delete_after=60.0, ephemeral=True)
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
    async def setChoiceError(self, ctx: ApplicationContext, exc: Exception):
        if isinstance(exc, CheckFailure):
            await ctx.respond("Du kannst keine Rolle auswählen. Entweder sind die 5 Minuten schon vorbei oder es wurde noch kein Spiel mit Rollenwahl gestartet.", delete_after=30, ephemeral=True)
        else:
            raise exc

    @commands.command(name="dead", aliases=["tot"])
    @has_role(getRoleID("gamemaster"))
    async def setDead(self, ctx: Context, player: Optional[Member]):
        """
        Der gegebene Spieler wird 'getötet'.
        Seine Rollen werden entfernt und ihm wird die Rolle 'tot' gegeben.
        Für die Chronik wird der Spieler auf 'tot' gesetzt.
        ``player``: Der zu tötende Spieler (optional)
        """
        gameCadre = getCurrentGameCadre()
        if player is None:
            livingPlayers: list[tuple] = [(x[0], list(gameCadre.keys()).index(x[0])) for x in gameCadre.items() if not x[1]["dead"]]
            playerNum = await takeSurvey(
                ctx, "Welchen Spieler willst du auf tot stellen?", livingPlayers
            )
            player = livingPlayers[playerNum]
        for role in player.roles:
            if self.checkRolePos(role, ctx.guild) and role.id != 768494431136645127:
                await player.remove_roles(role)
                await player.edit(mute=True)
        await player.add_roles(ctx.guild.get_role(getRoleID("dead")))
        # Der zwischengespeicherte Spielekader wird akktualisiert
        gameCadre[player]["dead"] = True
        setCurrentGameCadre(gameCadre)
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
            name="Rollen", value="\n".join(role.name for role in player.roles)
        )
        await ctx.send(embed=embed, delete_after=60.0)

    @commands.command(name="captain", aliases=["hauptmann", "cp"])
    @has_role(getRoleID("gamemaster"))
    async def setCaptain(self, ctx: Context, player: Optional[Member]):
        """
        Der gegebene Spieler wird die Rolle 'Hauptmann' gegeben.
        Für die Chronik wird der Spieler zum 'Hauptmann' gemacht.
        ``player``: Der Spieler, der zum Hauptmann wird (optional)
        """
        gameCadre = getCurrentGameCadre()
        if player is None:
            livingPlayers: list[tuple] = [(x[0], list(gameCadre.keys()).index(x[0])) for x in gameCadre.items() if not x[1]["dead"]]
            playerNum = await takeSurvey(
                ctx, "Welchen Spieler willst du zum Hauptmann machen?", livingPlayers
            )
            player = livingPlayers[playerNum]
        await player.add_roles(ctx.guild.get_role(getRoleID("captain")))
        gameCadre[player]["captain"] = True
        setCurrentGameCadre(gameCadre)
        embed = Embed(
            title="Erfolgreich zum Hauptmann befördert!",
            description=f"Der Spieler {player.display_name} wurde zum Hauptmann ernannt.",
            colour=Colour.orange(),
        )
        embed.add_field(
            name="Rollen", value="\n".join(role.name for role in player.roles)
        )
        await ctx.send(embed=embed, delete_after=60.0)

    @commands.command(name="chronicle", aliases=["chronik", "writeChronicle", "wrCr"])
    @has_role(getRoleID("gamemaster"))
    async def writeChronicle(self, ctx: Context, maxPlayers: Optional[int] = 20):
        """
        Die Chronik für dieses Spiel wird in den zugehörigen Kanal geschrieben.
        Es kann nur von dem letzten Spiel die Chronik geschrieben werden.
        Die Chronik kann nur richtig geschrieben werden, wenn der Bot durch die Befehle 'tot', 'hauptmann' und 'start' alle Informationen richtig bekommen hat.
        ``maxPlayers``: Die maximale Spielerzahl (optional) (default = 20)
        """
        gameCadre = getCurrentGameCadre()
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
                f" ({getElo(player.id)})" if getElo(player.id) is not None else " (No Elo)"
            )
            resultCadre[player.display_name] = value
        winner = "Niemand"
        if any(lovebirds := dict(n for n in gameCadre.items() if n[1]["lovebirds"])):
            teams = [getRoleTeam(value["role"]) for value in lovebirds.values()]
            if not teams.count("2") and all(not bird["dead"] for bird in lovebirds):
                winner = "Liebespaar"
        elif winner == "Niemand":
            livingTeams = set()
            for value in gameCadre.values():
                role, dead, captain, lovebirds = value.values()
                if not dead and not lovebirds:
                    livingTeams.add(getRoleTeam(role))
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
            maxPlayer=maxPlayers,
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
        await ctx.guild.get_channel(getChannelID("chronicle")).send(msg)
        gameNumber = saveCurrentGame(gameCadre, winner)
        self.bot.emitter.emit("calcElo", gameNumber)
        self.bot._current_gamemaster = None
        self.bot._lastRound = date.today()
        self.bot._ghostvoices = False
        await ctx.invoke(self.removeLovebirds)
        for player in gameCadre:
            nick: str = player.display_name
            await player.edit(nick=nick.removeprefix("♰"))
            await player.remove_roles(
                cast(Snowflake, list(map(
                    lambda x: cast(Role, x).id,
                    filter(
                        lambda x: x.id != getRoleID("gamemaster"),
                        player.roles
                    )
                ))[0])
            )
            if player.voice is not None:
                await player.edit(mute=False)
        setCurrentGameCadre({})

    @commands.command(name="love", aliases=["liebe", "liebende"])
    @has_role(getRoleID("gamemaster"))
    async def setLovebirds(self, ctx: Context, player1: Member, player2: Member):
        """
        Die beiden gegebenen Spieler werden das Liebespaar.
        Sie bekommen Zugang zum Liebespaar-Kanal.
        ``player1``: Der eine Spieler des Liebespaars
        ``player2``: Der andere Spieler des Liebespaars
        """
        loveChannel = ctx.guild.get_channel(getChannelID("lovebirds"))
        gameCadre = getCurrentGameCadre()
        await loveChannel.set_permissions(
            player1, send_messages=True, read_messages=True, read_message_history=True
        )
        await loveChannel.set_permissions(
            player2, send_messages=True, read_messages=True, read_message_history=True
        )
        gameCadre[player1]["lovebirds"] = True
        gameCadre[player2]["lovebirds"] = True
        setCurrentGameCadre(gameCadre)
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

    @commands.command(name="removeLove", aliases=["minusLove", "entferneLiebe", "rmLv"])
    @has_role(getRoleID("gamemaster"))
    async def removeLovebirds(self, ctx: Context):
        """
        Das Liebespaar wird aufgelöst.
        Der Zugang zum Liebespaar-Kanal wird für die Beiden wieder entfernt.
        """
        loveChannel = ctx.guild.get_channel(getChannelID("lovebirds"))
        gameCadre = getCurrentGameCadre()
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

    @commands.command(name="ghostvoices", aliases=["geisterstimmen", "gv", "gs"])
    @has_role(getRoleID("gamemaster"))
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

    @commands.command(name="reset", aliases=["resette", "restart"])
    @has_role(getRoleID("gamemaster"))
    async def resetRole(self, ctx: Context, player: Union[Member, str]):
        """
        Setzt den Spieler zum Stand am Anfang der Runde zurück.
        Wenn ein "all" hinzugefügt wird, dann wird die ganze Runde (alle Spieler) auf den Start der Runde zurückgesetzt.
        ``player``: Der Spieler, dessen Rolle zurückgesetzt werden soll, oder alle
        Möglichkeiten für ``player``: <ein Spieler>, 'all', 'alle', 'jeden'
        """
        if type(player) == str:
            if player.lower not in ("all", "alle", "jeden"):
                await ctx.send("""\tGibt bitte einen Spieler ein um diesen zurückzusetzen.
\tOder gibt eine der folgenden Möglichkeiten ein um das Spiel erneut zu starten: 'all', 'alle', 'jeden'""",
                               delete_after=20.0)
        cadre = getCurrentGameCadre()
        res_cadre = cadre.copy()
        if type(player) == str:
            title = "Das Spiel wurde zurückgesetzt"
            for ply, attrs in cadre.items():
                for attr, value in attrs.items():
                    if type(value) == bool:
                        res_cadre[ply][attr] = False
                for role in ply.roles:
                    if self.checkRolePos(role, ctx.guild):
                        await player.remove_roles(role)
                await player.add_roles(ctx.guild.get_role(getRoleID(attrs["role"])))
        else:
            title = "Der Spieler wurde zurückgesetzt"
            for attr, value in cadre[player].items():
                if type(value) == bool:
                    res_cadre[player][attr] = False
            for role in player.roles:
                if self.checkRolePos(role, ctx.guild):
                    await player.remove_roles(role)
                await player.add_roles(ctx.guild.get_role(getRoleID(cadre[player]["role"])))
        setCurrentGameCadre(res_cadre)
        embed = Embed(title=title,
                      description="Das Spiel sieht jetzt wie folgt aus:",
                      color=Colour.from_rgb(255, 0, 120))
        value = "\n".join(map(lambda m: f"{m[0].display_name}: {m[1]['role'].upper()}", res_cadre.items()))
        embed.add_field(name="Kader", value=value)
        await ctx.send(embed=embed, delete_after=60.0)

    @commands.command(name="setGamemaster", aliases=["sG"], hidden=True)
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


def setup(bot: My_Bot):
    bot.add_cog(Game(bot))


class RoleSelection(View):

    def __init__(self, *items: Item, timeout: Optional[float] = 180.0):
        super().__init__(*items, timeout=timeout)
        self.interaction: Interaction = None
        self.selected: str = None

    @discord.ui.select(
        placeholder="Choose a role or fraction you want to play",
        min_values=1,
        max_values=1,
        options=[SelectOption(label=x[0], description=x[1]) for x in
                 [(i.title(), "Rolle") for i in getCadre().keys()] + [("Dorf", "Fraktion"), ("Werwölfe", "Fraktion"), ("Drittpartei", "Fraktion")]] +
                [SelectOption(label="Keine Auswahl", description="Abbrechen der Auswahl, indem nichts gewählt wird", value="None", default=True)],
    )
    async def select_callable(self, select: Select, interaction: Interaction):
        self.stop()
        self.selected = select.values[0]
        self.interaction = interaction
