from numpy import average, e
from lib.bot.constants import BONI, NoPerms, getCurrentGameCadre
from lib.db.db import (
    getElo,
    getRoleID,
    getRoleTeam,
    getData,
    getLeagues
)
from random import choice
from discord import Embed, Member
from discord.ext.commands import Cog, command, Greedy, Context


class Elo(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.emitter.on("clacElo", self.calculateElo)

    @command(name="elo")
    async def getPlayerElo(self, ctx: Context, players: Greedy[Member]):
        """
        Gibt die Elo und den Rang des Autors oder des gegebenen Spielers zurück.
        Nur ein Spielleiter kann die Infos für einen anderen Spieler anfordern.
        ``players``: Eine Liste an Spielern mit Leerzeichen getrennt (optional)
        """
        leagues = getLeagues()
        if players == [] and (elo := getElo(ctx.author.id)) != None:
            embed = Embed(title="ELO Info", colour=choice(ctx.author.roles).colour)
            league = ""
            for name, range in leagues.items():
                if elo >= range[0] and elo <= range[1]:
                    league = name
            embed.add_field(
                name=ctx.author.display_name,
                value=f"Die ELO beträgt {elo}\nDaraus folgt der Rang {league}",
                inline=True,
            )
            await ctx.send(embed=embed, delete_after=45.0)
        elif players != [] and not any(
            role.id == getRoleID("gamemaster") for role in ctx.author.roles
        ):
            raise NoPerms(["Adminrechte"])
        elif players != [] and all(
            elo := tuple(getElo(player.id) for player in players)
        ):
            embed = Embed(title="ELO Info", colour=ctx.author.colour)
            fields = []
            for player in players:
                league = ""
                for name, range in leagues.items():
                    if (
                        elo[players.index(player)] >= range[0]
                        and elo[players.index(player)] <= range[1]
                    ):
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
                description="Grund: Nicht implementiert bisher.",
                colour=ctx.author.colour,
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
            await ctx.message.delete()

    @getPlayerElo.error
    async def getPlayerEloError(self, ctx: Context, exc):
        if isinstance(exc, NoPerms):
            await ctx.send(
                f"Du kannst keine Elo Infos zu anderen Personen holen, da dir folgende Berechtigung fehlt: {exc.message}",
                delete_after=30.0,
            )

    def eloDiff(teamElo: int, enemyElo: int, result: int):
        expect = round(1 / (1 + 10 ** ((enemyElo - teamElo) / 400)), 2)
        entwikl = (teamElo / 200) ** 4
        sbr = round(e ** ((1500 - teamElo) / 150) - 1)
        if teamElo < 1500 and result < expect:
            entwikl += sbr
        else:
            sbr = 0
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
            median = 0
            for elo in playerDict.values():
                median += elo
            return round(median / len(playerDict))

        def getOwnElo(playerElo: int, playerDict: dict):
            if playerElo < average(playerDict.values()):
                diff = round(
                    (average(playerDict.values()) - playerElo) * e ** -1
                    + round(
                        playerElo
                        / round(average(playerDict.values()))
                        * len(playerDict)
                        / 14,
                        4,
                    )
                )
                return round(playerElo + diff)
            elif playerElo == average(playerDict.values()):
                return playerElo
            else:
                diff = round(
                    (average(playerDict.values()) - playerElo) * e ** -1
                    + round(
                        playerElo
                        / round(average(playerDict.values()))
                        * len(playerDict)
                        / 14,
                        4,
                    )
                )
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
        return self.eloDiff(myElo, enemyElo, result)

    def getRanked(self, player: Member):
        playedGames = int(getData("players", ("PlayedGamesSeason"),("PlayerId", player.id)))
        if playedGames < 10:
            pass
        elif playedGames == 10:
            pass

    async def calculateElo(self, winner):
        cadre = getCurrentGameCadre()
        for player, plydict in cadre.items():
            cadre[player]["elo"] = getElo(player.id)
            cadre[player]["team"] = (
                getRoleTeam(plydict["role"])
                if not plydict["lovebirds"]
                else "Liebespaar"
            )
        for player, values in cadre.items():
            team = values["team"]
            role = values["role"]
            setPlayedGames(player.id)
            if (values["elo"] != None
                and getData("PlayedGamesSeason", "players", ("PlayerId", player.id)) < 10):
                setElo(player.id,values["elo"]+round(self.getELoDiff(player, cadre, 1 if team == winner else 0)*BONI[role.strip(" 12345-")]),)
            else:
                self.getRanked(player)

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("elo")


def setup(bot):
    bot.add_cog(Elo(bot))
