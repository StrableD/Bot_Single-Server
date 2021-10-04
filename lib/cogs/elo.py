import json

from discord.ext.commands import check
from lib.bot import My_Bot
from random import choice
from numpy import average, e
from lib.bot.constants import BONI, NoPerms
from lib.cogs.help import is_guild_owner
from lib.db.db import (
    getElo,
    getGameToEvaluate,
    getRoleID,
    getRoleTeam,
    getData,
    getLeagues,
    getUnevaluatedGames,
    setData,
    setGameToIsEvaluate,
    setPlayerElo
)
from discord import Embed, Member, Colour
from discord.ext.commands import Cog, command, Greedy, Context


class Elo(Cog):
    def __init__(self, bot: My_Bot):
        self.bot = bot
        self.__elo_calculated = False
                
        #emitter
        self.bot.emitter.on("calcElo", self.calculateElo)
        self.bot.emitter.on("newGame", self.set_calculated_to_false)
        
    @property
    def elo_calculated(self):
        return self.__elo_calculated

    @elo_calculated.setter
    def elo_calculated(self, value: bool):
        if type(value) == bool:
            self.__elo_calculated = value

    def set_calculated_to_false(self):
        self.elo_calculated = False
    
    @command(name="elo")
    async def getPlayerElo(self, ctx: Context, players: Greedy[Member]):
        """
        Gibt die Elo und den Rang des Autors oder des gegebenen Spielers zurück.
        Nur ein Spielleiter kann die Infos für einen anderen Spieler anfordern.
        ``players``: Eine Liste an Spielern mit Leerzeichen getrennt (optional)
        """
        leagues = getLeagues()
        if players == [] and (elo := getElo(ctx.author.id)) != None:
            embed = Embed(title="ELO Info", colour=Colour.from_rgb(154,7,125))
            embed.set_thumbnail(url=ctx.author.avatar_url)
            league = ""
            for name, range in leagues.items():
                if elo >= range[0] and elo <= range[1]:
                    league = name
            embed.add_field(
                name=ctx.author.display_name,
                value=f"Die ELO beträgt {elo}\nDaraus folgt der Rang **{league}**",
                inline=True,
            )
            embed.add_field(name="**Server**", value=ctx.guild.name, inline=False)
            await ctx.author.send(embed=embed, delete_after=45.0)
        elif players != [] and not any(role.id == getRoleID("gamemaster") for role in ctx.author.roles):
            raise NoPerms(["Adminrechte"])
        elif players != [] and all(elo := tuple(getElo(player.id) for player in players)):
            embed = Embed(title="ELO Info", colour=Colour.from_rgb(154,7,125))
            embed.set_thumbnail(url=choice(players).avatar_url)
            fields = []
            for player in players:
                league = ""
                for name, range in leagues.items():
                    if (elo[players.index(player)] >= range[0]
                        and elo[players.index(player)] <= range[1]):
                        league = name
                fields.append(
                    (player.display_name, (elo[players.index(player)], league), True)
                )

            for name, value, inline in fields:
                embed.add_field(
                    name=name,
                    value=f"Die ELO beträgt {value[0]}\nDaraus folgt der Rang {value[1]}",
                    inline=inline,
                )
            await ctx.send(embed=embed, delete_after=45.0)
        else:
            player = ctx.author if players == [] else players
            embed = Embed(
                title="Es gibt keine ELO Info",
                description="Grund: Bisher nicht implementiert oder du hast einfach keine ^^. \nBitte versuche es mit einer anderen Anfrage",
                colour=Colour.from_rgb(255,0,0),
            )
            player_without = []
            if isinstance(player, Member):
                player_without.append(player.display_name)
            else:
                for p in player:
                    if not getElo(p.id):
                        player_without.append(p.display_name)
            embed.add_field(
                name="Diese Spieler haben keine ELO"
                if len(player_without) != 1
                else "Dieser Spieler hat keine ELO",
                value=",".join(player_without),
                inline=True,
            )
            await ctx.send(embed=embed, delete_after=45.0)

    @getPlayerElo.error
    async def getPlayerEloError(self, ctx: Context, exc):
        if isinstance(exc, NoPerms):
            await ctx.send(
                f"Du kannst keine Elo Infos zu anderen Personen holen, da dir folgende Berechtigung fehlt: {exc.message}",
                delete_after=30.0,
            )
        else:
            raise exc

    def eloDiff(teamElo: int, enemyElo: int, result: int):
        expect = round(1 / (1 + 10 ** ((enemyElo - teamElo) / 400)), 2)
        entwikl = (teamElo / 200) ** 4
        
        sbr = round(e ** ((1500 - teamElo) / 150) - 1) if teamElo < 1500 and result < expect else 0
        entwikl += sbr
        
        if entwikl < 5:
            entwikl = 5
        elif sbr > 0 and entwikl >= 150:
            entwikl = 150
        elif sbr == 0 and entwikl >= 30:
            entwikl = 30
        
        discrep = round(1800 * (result - expect) / entwikl)
        if discrep < -35:
            discrep = -35

        return discrep

    def getELoDiff(self, player: Member, cadre: dict, result: int):
        def getMedian(playerDict: dict):
            median = sum(playerDict.values())
            return round(median / len(playerDict))

        def getOwnElo(playerElo: int, playerDict: dict):
            playersAverage = average(playerDict.values())
            diff = lambda: round((playersAverage-playerElo)*e**-1+round(playerElo/round(playersAverage)*len(playerDict)/14,4))
            if playerElo == playersAverage:
                return playerElo
            else:
                return round(playerElo + diff)

        playerDict = {}
        enemyDict = {}
        for ply, values in cadre.items():
            if values["team"] == cadre[player]["team"]:
                playerDict[ply] = values["elo"]
            else:
                enemyDict[ply] = values["elo"]
        myElo = getOwnElo(cadre[player]["elo"], playerDict)
        enemyElo = getMedian(enemyDict)
        elo = self.eloDiff(myElo, enemyElo, result)
        if result:
            elo = round(elo * BONI[cadre[player]["role"].strip(" 1234567890-").lower()])
        return elo

    def doRank(self, player: Member):
        playedGames, wonGames = getData("players", ("PlayedGamesSeason", "WonGameSeason"),("PlayerId", player.id))
        placementValue = 2*wonGames - playedGames
        elo = 1300 + placementValue * 50
        setPlayerElo(player.id, elo)

    def increaseGames(self, player: Member, role:str, win: bool):
        columns = ("PlayedGamesComplete", "WonGamesComplete", "PlayedGamesSeason", "WonGamesSeason", "WinsPerRole")
        compGames, compWin, seasGames, seasWin, winDict = getData("players", columns, ("PlayerID", player.id))
        winDict = json.loads(winDict)
        if win:
            winDict[role] = winDict[role] + 1 if role in winDict else 1
            compWin += 1
            seasWin += 1
        compGames += 1
        seasGames += 1
        winDict = json.dumps(winDict)
        setData("players", columns, (compGames,compWin,seasGames,seasWin,winDict), f"PlayerID = {player.id}")

    async def calculateElo(self, gameNumber: int):
        """Die Elo der Spieler wird hier am Ende eines Spieles berechnet und gespeichert"""
        if self.elo_calculated:
            return
        game = getGameToEvaluate(gameNumber)
        winner = game.pop("winner")
        for player in game:
            game[player]["team"] = getRoleTeam(game[player]["role"])
        for player in game:
            won = game[player]["team"] == winner
            self.increaseGames(player, game[player]["role"], won)
            if getData("players", ("PlayedGameSeason",), ("PlayerID", player.id))[0] <= 6:
                self.doRank(player)
            else:
                eloDiff = self.getELoDiff(player,game, int(won))
                newElo = game[player]["elo"]+ eloDiff
                setPlayerElo(player.id, newElo)
        setGameToIsEvaluate(gameNumber)
        self.elo_calculated = True
    
    @command(name="calcAllElo", aliases=["werteAlleAus", "waa","cae"])
    @check(is_guild_owner)
    async def calculateAllElo(self, ctx: Context):
        """
        Mit diesem Befehl können alle nicht ausgewerteten Spiele ausgewerted werden.
        """
        members = set()
        gameNums = getUnevaluatedGames()
        for gameNum in gameNums:
            self.elo_calculated = False
            game = [getGameToEvaluate(gameNum).keys()].remove("winner")
            members.update(game)
            await self.calculateElo(gameNum)
        
        embed = Embed(title="Elo ausgewerted",
                      desciption="Die Elo der noch nicht ausgewerteten Spiele wurde berechnet",
                      colour=Colour.form_rgb(0,0,0))
        embed.add_field(name="Anzahl ausgewerteter Spiele", value=sum(gameNums))
        embed.add_field(name="Von diesen Spielern wurde die Elo geändert",
                        value="\n".join(map(lambda x: x.display_name if members.index(x) % 2 != 0 else f"\t{x.display_name}", members)),
                        inline=False)
        await ctx.send(embed=embed, delete_after=100.0)
        

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("elo")


def setup(bot):
    bot.add_cog(Elo(bot))
