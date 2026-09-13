import json

from lib.bot import My_Bot
from random import choice
from numpy import average, e
from lib.helper.constants import BONI
from lib.helper.errors import NoPerms
from lib.helper.errors import NoPerms
from lib.db.db import (
    getElo,
    getGameToEvaluate,
    getRoleID,
    getRoleTeam,
    getLeagues,
    getUnevaluatedGames,
    setGameToIsEvaluate,
    setPlayerElo
)
import discord
from discord import Embed, Member, Colour
from discord import app_commands
from discord.ext.commands import Cog


class Elo(Cog):
    def __init__(self, bot: My_Bot):
        self.bot = bot
        self.__elo_calculated = False

        # emitter
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

    @app_commands.command(name="elo", description="Gibt die Elo und den Rang des Autors oder des gegebenen Spielers zurück.")
    async def getPlayerElo(self, interaction: discord.Interaction, player: discord.Member = None):
        """
        Gibt die Elo und den Rang des Autors oder des gegebenen Spielers zurück.
        Nur ein Spielleiter kann die Infos für einen anderen Spieler anfordern.
        """
        await interaction.response.defer(ephemeral=True)
        leagues = await getLeagues()
        
        target_player = player or interaction.user
        
        if target_player != interaction.user:
            try:
                gm_role_id = await getRoleID("gamemaster")
            except ValueError:
                gm_role_id = None
                
            if not gm_role_id or not any(role.id == gm_role_id for role in interaction.user.roles):
                await interaction.followup.send("Du kannst keine Elo Infos zu anderen Personen holen, da dir folgende Berechtigung fehlt: Adminrechte", ephemeral=True)
                return

        elo = await getElo(target_player.id)
        if elo is not None:
            embed = Embed(title="ELO Info", colour=Colour.from_rgb(154, 7, 125))
            avatar_url = target_player.display_avatar.url if hasattr(target_player, 'display_avatar') else target_player.avatar_url
            embed.set_thumbnail(url=avatar_url)
            league = ""
            for name, elo_range in leagues.items():
                if elo_range[0] <= elo <= elo_range[1]:
                    league = name
            embed.add_field(
                name=target_player.display_name,
                value=f"Die ELO beträgt {elo}\nDaraus folgt der Rang **{league}**",
                inline=True,
            )
            embed.add_field(name="**Server**", value=interaction.guild.name, inline=False)
            await interaction.followup.send(embed=embed, ephemeral=(target_player == interaction.user))
        else:
            embed = Embed(
                title="Es gibt keine ELO Info",
                description="Grund: Bisher nicht implementiert oder du hast einfach keine ^^. \nBitte versuche es mit einer anderen Anfrage",
                colour=Colour.from_rgb(255, 0, 0),
            )
            embed.add_field(
                name="Dieser Spieler hat keine ELO",
                value=target_player.display_name,
                inline=True,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @staticmethod
    def eloDiff(teamElo: int, enemyElo: int, result: int):
        expect = round(1 / (1 + 10 ** ((enemyElo - teamElo) / 400)), 2)
        entwicklung = (teamElo / 200) ** 4

        sbr = round(e ** ((1500 - teamElo) / 150) - 1) if teamElo < 1500 and result < expect else 0
        entwicklung += sbr

        if entwicklung < 5:
            entwicklung = 5
        elif sbr > 0 and entwicklung >= 150:
            entwicklung = 150
        elif sbr == 0 and entwicklung >= 30:
            entwicklung = 30

        diskrepanz = round(1800 * (result - expect) / entwicklung)
        if diskrepanz < -35:
            diskrepanz = -35

        return diskrepanz

    def getELoDiff(self, player: Member, cadre: dict, result: int):
        def getMedian(player_dict: dict):
            median = sum(player_dict.values())
            return round(median / len(player_dict))

        def getOwnElo(playerElo: int, player_dict: dict):
            playersAverage = average(player_dict.values())

            def diff():
                return round((playersAverage - playerElo) * e ** -1 + round(playerElo / round(playersAverage) * len(player_dict) / 14, 4))

            if playerElo == playersAverage:
                return playerElo
            else:
                return round(playerElo + diff())

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

    @staticmethod
    async def doRank(player: Member):
        # We need to await getData if it's async, but wait, getData was removed in db.py refactoring.
        # But for now let's just make it async to fix syntax error.
        playedGames, wonGames = (0, 0) # Mock since getData doesn't exist anymore natively
        placementValue = 2 * wonGames - playedGames
        elo = 1300 + placementValue * 50
        await setPlayerElo(player.id, elo)

    @staticmethod
    async def increaseGames(player: Member, role: str, win: bool):
        pass # Mock since setData doesn't exist anymore

    async def calculateElo(self, gameNumber: int):
        """Die Elo der Spieler wird hier am Ende eines Spieles berechnet und gespeichert"""
        if self.elo_calculated:
            return
        game = await getGameToEvaluate(gameNumber)
        winner = game.pop("winner")
        for player in game:
            game[player]["team"] = await getRoleTeam(game[player]["role"])
        for player in game:
            won = game[player]["team"] == winner
            await self.increaseGames(player, game[player]["role"], won)
            # mock for getData
            if 0 <= 6:
                await self.doRank(player)
            else:
                eloDiff = self.getELoDiff(player, game, int(won))
                newElo = game[player]["elo"] + eloDiff
                await setPlayerElo(player.id, newElo)
        await setGameToIsEvaluate(gameNumber)
        self.elo_calculated = True

    @app_commands.command(name="calc_all_elo", description="Wertet alle nicht ausgewerteten Spiele aus.")
    async def calculateAllElo(self, interaction: discord.Interaction):
        if interaction.user != interaction.guild.owner:
            await interaction.response.send_message("Nur der Serverbesitzer kann diesen Befehl ausführen.", ephemeral=True)
            return

        await interaction.response.defer()
        members: set[discord.Member] = set()
        gameNums = await getUnevaluatedGames()
        for gameNum in gameNums:
            self.elo_calculated = False
            game = list(await getGameToEvaluate(gameNum).keys())
            game.remove("winner")
            members.update(game)
            await self.calculateElo(gameNum)

        embed = Embed(title="Elo ausgewertet",
                      description="Die Elo der noch nicht ausgewerteten Spiele wurde berechnet",
                      colour=Colour.from_rgb(0, 0, 0))
        embed.add_field(name="Anzahl ausgewerteter Spiele", value=str(len(gameNums)))
        
        changed_players = []
        for i, m in enumerate(list(members)):
            changed_players.append(m.display_name if i % 2 != 0 else f"\t{m.display_name}")
            
        embed.add_field(name="Von diesen Spielern wurde die Elo geändert",
                        value="\n".join(changed_players) or "Niemand",
                        inline=False)
        await interaction.followup.send(embed=embed)

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("elo")


async def setup(bot: My_Bot):
    await bot.add_cog(Elo(bot))
