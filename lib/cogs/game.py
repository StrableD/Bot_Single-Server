from datetime import date, datetime, timedelta
from lib.cogs.help import is_guild_owner
from typing import Optional, Union

from apscheduler.triggers.date import DateTrigger
from discord import Colour, Embed, Guild, Member, Role
from discord.ext.commands import Bot, Cog, Context, command, check
from discord.ext.commands.core import has_role
from lib.bot import My_Bot
from lib.bot.constants import (
    CHRONICLE_PATTERN,
    InputError,
    getCadre,
    getCurrentGameCadre,
    setCurrentGameCadre,
)
from lib.cogs.settings import takeSurvey
from lib.db.db import getChannelID, getElo, getRoleID, getRoleTeam, saveCurrentGame 
from numpy.random import randint


class Game(Cog):
    """
    Das Modul, welches die Funktionen zum Spielen hinzufügt.
    """

    def __init__(self, bot: My_Bot):
        self.bot = bot

    @property
    def cadreLength(self) -> int:
        cadre = getCadre()
        length = 0
        for num in cadre.values():
            length += num
        return length

    @staticmethod
    def getSquad(players: list) -> dict[str, str]:
        returnDict = {}
        length = len(players)
        for player in players:
            rand = randint(length)
            while rand in returnDict.values():
                rand = randint(length)
            returnDict[player] = rand
            # returnDict[player]=f"Werwolf-{players.index(player)+1}"
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
        currentCadre = {}
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
    def checkRolePos(role: Role, guild: Guild):
        if role.position >= guild.get_role(getRoleID("dead")).position:
            return True
        return False

    @command(name="start", aliases=["go", "starten"])
    @has_role(getRoleID("gamemaster"))
    async def startGame(self, ctx: Context):
        """
        Die Funktion startet das Spiel.
        Gestartet wird mit dem bisher ausgewählten Kader und den Spielern, die mit dem Spielleiter (Autor) in einem Sprachkanal sind.
        Es setzt außerdem den Kader für die Chronik und den Spielleiter.
        """
        if ctx.author.voice == None:
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
                desciption="Für ein Spiel benötigt ihr noch mehr Spieler in dem Kanal.",
                colour=Colour.from_rgb(255,0,0),
            )
            embed.add_field(
                name="Anzahl fehlender Spieler",
                value=self.cadreLength - len(playerList),
            )
            embed.add_field(
                name="Mögliche Lösungen",
                value="Ihr könntet mehr Spieler in den Sprachkanal holen oder die Kadergröße runterstellen.",
            )
            await ctx.send(embed=embed, delete_after=30.0)
            return
        
        elif len(playerList) > self.cadreLength:
            embed = Embed(
                title="Kein Spielstart möglich",
                desciption="Für ein Spiel habt ihr zu viele Spieler in dem Kanal.",
                colour=Colour.from_rgb(255,0,0),
            )
            embed.add_field(
                name="Anzahl überzähliger Spieler",
                value=len(playerList) - self.cadreLength(),
            )
            embed.add_field(
                name="Mögliche Lösungen",
                value="Ihr könntet Spieler aus dem Sprachkanal entfernen oder die Kadergröße erhöhen.",
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
                await player.move_to(GVoiceChannel)
            await ctx.author.move_to(GVoiceChannel)
            await ctx.send(
                "Alle Spieler sind im Sprachkanal und das Spiel kann beginnen",
                delete_after=60.0,
            )
            self.bot.emitter.emit("newGame")
            self.bot._current_gamemaster = ctx.author

    @command(name="dead", aliases=["tot"])
    @has_role(getRoleID("gamemaster"))
    async def setDead(self, ctx: Context, player: Optional[Member]):
        """
        Der gegebene Spieler wird 'getötet'.
        Seine Rollen werden entfernt und ihm wird die Rolle 'tot' gegeben.
        Für die Chronik wird der Spieler auf 'tot' gesetzt.
        ``player``: Der zu tötende Spieler (optional)
        """
        gameCadre = getCurrentGameCadre()
        if player == None:
            livingPlayers = list(
                map(
                    lambda x: (x[0], gameCadre.keys().index(x[0]))
                    if not x[1]["dead"]
                    else None,
                    gameCadre.items()
                )
            ).remove(None)
            playerNum = await takeSurvey(
                ctx, "Welchen Spieler willst du auf tot stellen?", livingPlayers
            )
            player = livingPlayers[playerNum]
        for role in player.roles:
            if self.checkRolePos(role, ctx.guild) and role.id != 768494431136645127:
                await player.remove_roles(role)
                await player.edit(mute=True)
        await player.add_roles(ctx.guild.get_role(getRoleID("dead")))
        #Der zwischengespeicherte Spielekader wird akktualisiert
        gameCadre[player]["dead"] = True
        setCurrentGameCadre(gameCadre)
        #Der Nickname des Spielers wird geändert
        nick = player.display_name
        await player.edit(nick=f"♰ {nick}")
        #Die Nachricht des erfolgreichen Tötens wird gesendet
        embed = Embed(
            title="Erfolgreich getötet!",
            description=f"Der Spieler {player.name} wurde getötet.",
            colour=Colour.from_rgb(0,0,0),
        )
        embed.add_field(
            name="Rollen", value="\n".join(role.name for role in player.roles)
        )
        await ctx.send(embed=embed, delete_after=60.0)

    @command(name="captain", aliases=["hauptmann", "cp"])
    @has_role(getRoleID("gamemaster"))
    async def setCaptain(self, ctx: Context, player: Optional[Member]):
        """
        Der gegebene Spieler wird die Rolle 'Hauptmann' gegeben.
        Für die Chronik wird der Spieler zum 'Hauptmann' gemacht.
        ``player``: Der Spieler, der zum Hauptmann wird (optional)
        """
        gameCadre = getCurrentGameCadre()
        if player == None:
            livingPlayers = list(
                map(
                    lambda x: (x[0], gameCadre.keys().index(x[0]))
                    if not x[1]["dead"]
                    else None,
                    gameCadre.items(),
                )
            ).remove(None)
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

    @command(name="chronicle", aliases=["chronik", "writeChronicle", "wrCr"])
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
                    colour=Colour.from_rgb(255,0,0),
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
                f" ({getElo(player.id)})" if getElo(player.id) != None else " (No Elo)"
            )
            resultCadre[player.display_name] = value
        winner = "Niemand"
        if any(lovebirds := dict(filter(lambda n: n[1]["lovebirds"], gameCadre.items()))):
            teams = [getRoleTeam(value["role"]) for value in lovebirds.values()]
            if not teams.count(2) and all(not bird["dead"] for bird in lovebirds):
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
                ctx.send(
                    "Es kann kein Gewinner ermittelt werden. Stelle alle, die verloren haben bitte auf 'tot' und versuch es erneut"
                )
                return
        if date.today() == self.bot._lastRound:
            self.bot._roundNum += 1
        else:
            self.bot._roundNum = 1
        msg = CHRONICLE_PATTERN.format(
            datum=date.today().strftime("%A, %d.%m.%Y"),
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
            nick:str = player.display_name
            await player.edit(nick=nick.removeprefix("♰"))
            await player.remove_roles((filter(lambda x: x.id != getRoleID("gamemaster"), player.roles)))
            if player.voice != None:
                await player.edit(mute=False)
        setCurrentGameCadre({})

    @command(name="love", aliases=["liebe", "liebende"])
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
                colour=Colour.from_rgb(252,15,192),
            ).add_field(
                name="Spieler:", value=f"{player1.display_name}\n{player2.display_name}"
            ),
            delete_after=60.0,
        )

    @command(name="removeLove", aliases=["minusLove", "entferneLiebe", "rmLv"])
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
                colour=Colour.from_rgb(255,0,120),
            ).add_field(name="Spieler:", value="\n".join(removedPlayer)),
            delete_after=60.0,
        )

    @command(name="ghostvoices", aliases=["geisterstimmen", "gv", "gs"])
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
    
    @command(name="reset", aliases=["resette", "restart"])
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
                        res_cadre[ply][attr] = not value
                for role in ply.roles:
                    if self.checkRolePos(role, ctx.guild):
                        await player.remove_roles(role)
                await player.add_roles(ctx.guild.get_role(getRoleID(attr["role"])))
        else:
            title = "Der Spieler wurde zurückgesetzt"
            for attr, value in cadre[player].items():
                if type(value) == bool:
                    res_cadre[player][attr] = not value
            for role in player.roles:
                if self.checkRolePos(role, ctx.guild):
                    await player.remove_roles(role)
                await player.add_roles(ctx.guild.get_role(getRoleID(cadre[player]["role"])))
        setCurrentGameCadre(res_cadre)
        embed = Embed(title=title,
                      description="Das Spiel sieht jetzt wie folgt aus:",
                      color=Colour.from_rgb(255,0,120))
        value = "\n".join(map(lambda m: f"{m[0].display_name}: {m[1]['role'].upper()}", res_cadre.items()))
        embed.add_field(name="Kader",value=value)
        await ctx.send(embed=embed, delete_after=60.0)

    @command(name="setGamemaster", aliases=["sG"], hidden=True)
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


def setup(bot: Bot):
    bot.add_cog(Game(bot))
