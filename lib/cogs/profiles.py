import discord
from discord.ext import commands
from discord.ext.commands import Context
from lib.db.db import AsyncSessionLocal
from lib.db.models import Player, League
from sqlalchemy import select

class PlayerProfilesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="profile")
    async def profile(self, ctx: Context, member: discord.Member = None):
        """Displays a rich player profile with Match History and Rank."""
        target = member or ctx.author
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Player).where(Player.PlayerId == target.id))
            player_data = result.scalar_one_or_none()
            
            if not player_data:
                await ctx.send(f"{target.display_name} has no recorded games or Elo.", ephemeral=True)
                return

            result = await session.execute(select(League))
            leagues = result.scalars().all()
            
            current_league = "Unranked"
            for l in leagues:
                if (l.LowestElo or 0) <= player_data.Elo <= (l.HighestElo or 10000):
                    current_league = l.LeagueName
                    break
            
            win_rate = (player_data.WonGamesComplete / player_data.PlayedGamesComplete * 100) if player_data.PlayedGamesComplete > 0 else 0
            
            embed = discord.Embed(
                title=f"Player Profile: {target.display_name}", 
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=target.display_avatar.url if target.display_avatar else target.default_avatar.url)
            embed.add_field(name="Current Rank", value=f"{current_league} ({player_data.Elo} Elo)", inline=False)
            embed.add_field(name="Total Games", value=str(player_data.PlayedGamesComplete), inline=True)
            embed.add_field(name="Win Rate", value=f"{win_rate:.1f}%", inline=True)
            
            # Button to share profile
            view = discord.ui.View()
            btn = discord.ui.Button(label="Share to Channel", style=discord.ButtonStyle.success)
            
            async def share_callback(interaction):
                await interaction.channel.send(embed=embed)
                await interaction.response.send_message("Profile shared!", ephemeral=True)
                
            btn.callback = share_callback
            view.add_item(btn)
            
            await ctx.send(embed=embed, view=view, ephemeral=True)

    @commands.hybrid_command(name="leaderboard")
    async def leaderboard(self, ctx: Context, public: bool = False):
        """Displays the server's top players by Elo ranking."""
        # If user is not GM, ignore public flag and force ephemeral
        gm_role = discord.utils.get(ctx.guild.roles, name="gamemaster") # rough check
        if gm_role not in ctx.author.roles:
            public = False
            
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Player).order_by(Player.Elo.desc()).limit(10))
            players = result.scalars().all()
            
            if not players:
                await ctx.send("No players ranked yet.", ephemeral=True)
                return
                
            embed = discord.Embed(title="Server Leaderboard - Top 10", color=discord.Color.blue())
            
            desc = ""
            for i, p in enumerate(players, 1):
                desc += f"**{i}.** {p.PlayerName} - {p.Elo} Elo\\n"
            
            embed.description = desc
            await ctx.send(embed=embed, ephemeral=not public)

async def setup(bot):
    await bot.add_cog(PlayerProfilesCog(bot))
