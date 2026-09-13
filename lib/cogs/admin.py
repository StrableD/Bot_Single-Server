import discord
from discord import app_commands
from discord.ext.commands import Cog
from lib.bot import My_Bot
from lib.helper.constants import ALL_ROLES
from lib.db.db import AsyncSessionLocal
from lib.db.models import Role, Channel
from sqlalchemy import select

class Admin(Cog):
    def __init__(self, bot: My_Bot):
        self.bot = bot
        # Creating a group inside __init__ is fine, but we actually should decorate methods inside the group or cog
        # Using app_commands.Group
        
    admin_group = app_commands.Group(name="admin", description="Admin & Setup commands")

    @admin_group.command(name="setup", description="Run the server setup wizard to initialize the bot.")
    async def setup_wizard(self, interaction: discord.Interaction):
        if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only the Server Owner or an Administrator can run the setup wizard.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        
        # 1. Create a "Gamemaster" role if it doesn't exist
        gm_role = discord.utils.get(interaction.guild.roles, name="Gamemaster")
        if not gm_role:
            try:
                gm_role = await interaction.guild.create_role(name="Gamemaster", color=discord.Color.purple(), hoist=True)
            except discord.Forbidden:
                await interaction.followup.send("I do not have permissions to create roles! Please give me Administrator permissions.")
                return

        # 2. Add all roles to DB
        async with AsyncSessionLocal() as session:
            # Sync Gamemaster role
            result = await session.execute(select(Role).where(Role.name_bot == "gamemaster"))
            db_gm_role = result.scalar_one_or_none()
            if not db_gm_role:
                db_gm_role = Role(name_bot="gamemaster", id=gm_role.id, name_guild="Gamemaster", team="gamemaster")
                session.add(db_gm_role)
            else:
                db_gm_role.id = gm_role.id
            
            # Sync all known standard roles to DB if missing
            for role_name in ALL_ROLES:
                bot_name = role_name.lower().replace("-", "").replace(" ", "")
                result = await session.execute(select(Role).where(Role.name_bot == bot_name))
                db_role = result.scalar_one_or_none()
                if not db_role:
                    # Creating a dummy discord role for each is overwhelming, so we just add to DB 
                    # with ID=0 to indicate it's missing in Discord, allowing GM to map it later.
                    db_role = Role(name_bot=bot_name, id=0, name_guild=role_name, team="unknown")
                    session.add(db_role)
            
            await session.commit()
            
        await interaction.followup.send("✅ Setup Wizard completed! Gamemaster role created and standard roles populated in the database. You can now use `/admin config` to map existing Discord roles to the bot's roles.")

async def setup(bot: My_Bot):
    await bot.add_cog(Admin(bot))
