from lib.bot import My_Bot
from lib.db.db import (
    getElo,
    getRoleID,
    getLeagues
)
import discord
from discord import Embed, Member, Colour
from discord import app_commands
from discord.ext.commands import Cog

class Elo(Cog):
    def __init__(self, bot: My_Bot):
        self.bot = bot

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
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("Dieser Spieler hat noch keine Elo.", ephemeral=True)

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("elo")

async def setup(bot: My_Bot):
    await bot.add_cog(Elo(bot))
