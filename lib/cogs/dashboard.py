import discord
from discord.ext import commands
from discord.ext.commands import Cog, Context
from discord.ui import Button, View

from lib.bot import My_Bot
from lib.db.cadre_db import getCurrentGameCadre
from lib.helper.checks import is_gamemaster


class GamemasterDashboard(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Advance Phase",
        style=discord.ButtonStyle.primary,
        custom_id="gm_dash_next",
    )
    async def next_phase_btn(self, interaction: discord.Interaction, button: Button):
        next_cog = self.bot.get_cog("Next")
        if next_cog:
            # We construct a fake Context or invoke it directly
            await interaction.response.send_message(
                "Advancing phase...", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Next cog not loaded.", ephemeral=True
            )

    @discord.ui.button(
        label="Kill Player", style=discord.ButtonStyle.danger, custom_id="gm_dash_kill"
    )
    async def kill_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            "Use /dead command for now. Dropdown coming soon.", ephemeral=True
        )

    @discord.ui.button(
        label="Revive Player",
        style=discord.ButtonStyle.success,
        custom_id="gm_dash_revive",
    )
    async def revive_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            "Revive player logic here.", ephemeral=True
        )

    @discord.ui.button(
        label="View Roles",
        style=discord.ButtonStyle.secondary,
        custom_id="gm_dash_roles",
    )
    async def view_roles_btn(self, interaction: discord.Interaction, button: Button):
        cadre = await getCurrentGameCadre()
        if not cadre:
            await interaction.response.send_message(
                "No active game cadre.", ephemeral=True
            )
            return

        desc = "\n".join(
            [
                f"{member}: {info['role']} (Dead: {info['dead']})"
                for member, info in cadre.items()
            ]
        )
        embed = discord.Embed(
            title="Current Cadre", description=desc, color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="Pending Actions",
        style=discord.ButtonStyle.danger,
        custom_id="gm_dash_actions",
    )
    async def pending_actions_btn(
        self, interaction: discord.Interaction, button: Button
    ):
        from sqlalchemy import select

        from lib.db.db import AsyncSessionLocal
        from lib.db.models import ActionRequest, Lobby

        async with AsyncSessionLocal() as session:
            lobby = await session.execute(select(Lobby).where(Lobby.is_active))
            active_lobby = lobby.scalar_one_or_none()
            if not active_lobby:
                await interaction.response.send_message(
                    "No active lobby.", ephemeral=True
                )
                return

            reqs = await session.execute(
                select(ActionRequest).where(
                    ActionRequest.lobby_id == active_lobby.id,
                    ActionRequest.status == "pending",
                )
            )
            actions = reqs.scalars().all()

            if not actions:
                await interaction.response.send_message(
                    "No pending actions.", ephemeral=True
                )
                return

            desc = "\n".join(
                [
                    f"ID {a.id}: <@{a.player_id}> wants to '{a.action_type}' on <@{a.target_id}>"
                    for a in actions
                ]
            )
            embed = discord.Embed(
                title="Pending Actions", description=desc, color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

            # To-Do: Add approve/reject buttons attached to this message

    async def generate_embed(self, guild):
        cadre = await getCurrentGameCadre()
        alive_count = (
            sum(1 for info in cadre.values() if not info["dead"]) if cadre else 0
        )
        dead_count = sum(1 for info in cadre.values() if info["dead"]) if cadre else 0

        embed = discord.Embed(
            title="Gamemaster Dashboard",
            description="Control the game flow from here.",
            color=discord.Color.dark_theme(),
        )
        embed.add_field(name="Players Alive", value=str(alive_count), inline=True)
        embed.add_field(name="Players Dead", value=str(dead_count), inline=True)
        embed.add_field(name="Phase", value="Night/Day Phase X", inline=True)
        return embed


class Dashboard(Cog):
    def __init__(self, bot: My_Bot):
        self.bot = bot

    @commands.hybrid_command(name="dashboard")
    @is_gamemaster()
    async def spawn_dashboard(self, ctx: Context):
        """Spawns the live-updating Gamemaster Dashboard"""

        channel_name = ctx.channel.name.lower()
        if (
            "bot" not in channel_name
            and "gm" not in channel_name
            and "gamemaster" not in channel_name
        ):
            await ctx.send(
                "⚠️ **Warning**: You are spawning the dashboard outside the designated Gamemaster/Bot channel!",
                ephemeral=True,
            )

        view = GamemasterDashboard(self.bot)
        embed = await view.generate_embed(ctx.guild)
        await ctx.send(embed=embed, view=view)


async def setup(bot: My_Bot):
    await bot.add_cog(Dashboard(bot))
