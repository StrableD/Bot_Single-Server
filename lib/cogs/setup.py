import discord
from discord.ext import commands
from discord.ext.commands import Cog, Context
from discord.ui import View, Button
from lib.bot import My_Bot
from lib.db.db import AsyncSessionLocal
from lib.db.models import Channel, Role
from sqlalchemy import update, select

class SetupWizard(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Auto-Setup Server", style=discord.ButtonStyle.success, custom_id="setup_auto")
    async def auto_setup_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Starting Auto-Setup... (This will create categories, channels, and roles)", ephemeral=True)
        # Skeleton for auto-setup logic
        # - Create 'Werewolf' Category
        # - Create 'gamemaster', 'bot_channel', 'graveyard'
        # - Create role channels for Seer, Witch, etc.
        # - Update DB with mapped IDs
        pass

    @discord.ui.button(label="Manual Mapping", style=discord.ButtonStyle.primary, custom_id="setup_manual")
    async def manual_setup_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Manual mapping selected. Please use `/config remap` to map channels/roles.", ephemeral=True)

class SetupCog(Cog):
    def __init__(self, bot: My_Bot):
        self.bot = bot

    @commands.hybrid_command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup_wizard(self, ctx: Context):
        """Initiate the bot setup wizard for the server."""
        embed = discord.Embed(
            title="🛠️ Server Setup Wizard", 
            description="Welcome to the Werewolf Bot Setup! Would you like the bot to automatically generate all required roles and channels, or do you want to map existing ones?",
            color=discord.Color.blurple()
        )
        view = SetupWizard(self.bot)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_group(name="config")
    @commands.has_permissions(administrator=True)
    async def config(self, ctx: Context):
        """Configure bot mappings and game settings."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Use `/config remap_channel` or `/config remap_role`.", ephemeral=True)

    @config.command(name="remap_channel")
    async def remap_channel(self, ctx: Context, bot_internal_name: str, channel: discord.TextChannel):
        """Remap a bot-internal channel name to a Discord channel."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Channel).where(Channel.name_bot == bot_internal_name))
            record = result.scalar_one_or_none()
            if record:
                record.id = channel.id
                await session.commit()
                await ctx.send(f"Successfully remapped `{bot_internal_name}` to {channel.mention}.")
            else:
                new_channel = Channel(name_bot=bot_internal_name, id=channel.id, name_guild=channel.name, private=False)
                session.add(new_channel)
                await session.commit()
                await ctx.send(f"Successfully created mapping `{bot_internal_name}` to {channel.mention}.")

    @config.command(name="remap_role")
    async def remap_role(self, ctx: Context, bot_internal_name: str, role: discord.Role):
        """Remap a bot-internal role name to a Discord role."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Role).where(Role.name_bot == bot_internal_name))
            record = result.scalar_one_or_none()
            if record:
                record.id = role.id
                await session.commit()
                await ctx.send(f"Successfully remapped `{bot_internal_name}` to {role.mention}.")
            else:
                new_role = Role(name_bot=bot_internal_name, id=role.id, name_guild=role.name, synonyms="[]", team="Unknown")
                session.add(new_role)
                await session.commit()
                await ctx.send(f"Successfully created mapping `{bot_internal_name}` to {role.mention}.")

async def setup(bot: My_Bot):
    await bot.add_cog(SetupCog(bot))
