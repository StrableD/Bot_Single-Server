import discord
from discord import app_commands
from discord.ext.commands import Cog
from typing import List, Optional

from lib.bot import My_Bot
from lib.helper.constants import ALL_ROLES
from lib.db.db import AsyncSessionLocal
from lib.db.models import Role as DBRole
from sqlalchemy import select

# --- UI Views ---

class SetupWizard(discord.ui.View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=900)
        self.original_interaction = interaction
        # Roles we need to map
        self.pending_roles = ["Gamemaster"] + ALL_ROLES
        self.current_idx = 0
        self.mode = None # "auto" or "manual"
        
    async def start(self):
        embed = discord.Embed(
            title="Setup Wizard",
            description="Welcome! Would you like to run the Automatic or Manual setup?\n\n"
                        "**Automatic**: I will try to guess your roles and ask if I should create them if missing.\n"
                        "**Manual**: I will walk through every role and let you pick the Discord role from a dropdown.",
            color=discord.Color.blue()
        )
        btn_auto = discord.ui.Button(label="Automatic", style=discord.ButtonStyle.green)
        btn_manual = discord.ui.Button(label="Manual", style=discord.ButtonStyle.blurple)
        
        async def auto_cb(i: discord.Interaction):
            self.mode = "auto"
            self.clear_items()
            await i.response.edit_message(content="Starting Automatic Setup...", embed=None, view=self)
            await self.next_step(i)
        
        async def manual_cb(i: discord.Interaction):
            self.mode = "manual"
            self.clear_items()
            await i.response.edit_message(content="Starting Manual Setup...", embed=None, view=self)
            await self.next_step(i)
            
        btn_auto.callback = auto_cb
        btn_manual.callback = manual_cb
        
        self.add_item(btn_auto)
        self.add_item(btn_manual)
        
        await self.original_interaction.followup.send(embed=embed, view=self, ephemeral=True)

    async def next_step(self, interaction: discord.Interaction):
        if self.current_idx >= len(self.pending_roles):
            await interaction.edit_original_response(content="✅ Setup Complete! All roles have been mapped.", embed=None, view=None)
            return
            
        current_role_name = self.pending_roles[self.current_idx]
        self.clear_items()
        
        if self.mode == "auto":
            await self.handle_auto_step(interaction, current_role_name)
        else:
            await self.handle_manual_step(interaction, current_role_name)

    async def save_role_to_db(self, bot_name: str, guild_name: str, discord_role_id: int):
        async with AsyncSessionLocal() as session:
            bot_name_clean = bot_name.lower().replace("-", "").replace(" ", "")
            result = await session.execute(select(DBRole).where(DBRole.name_bot == bot_name_clean))
            db_role = result.scalar_one_or_none()
            if not db_role:
                db_role = DBRole(name_bot=bot_name_clean, id=discord_role_id, name_guild=guild_name, team="unknown")
                session.add(db_role)
            else:
                db_role.id = discord_role_id
                db_role.name_guild = guild_name
            await session.commit()

    async def handle_auto_step(self, interaction: discord.Interaction, role_name: str):
        # Try to guess
        guild = interaction.guild
        guessed_role = None
        for r in guild.roles:
            # Simple string match
            if role_name.lower() in r.name.lower():
                guessed_role = r
                break
                
        if guessed_role:
            embed = discord.Embed(title=f"Role Setup: {role_name}", description=f"I guessed this matches your existing Discord role: {guessed_role.mention}\nIs this correct?", color=discord.Color.gold())
            
            btn_yes = discord.ui.Button(label="Yes", style=discord.ButtonStyle.green)
            btn_no = discord.ui.Button(label="No, ask to create", style=discord.ButtonStyle.danger)
            
            async def yes_cb(i: discord.Interaction):
                await self.save_role_to_db(role_name, guessed_role.name, guessed_role.id)
                self.current_idx += 1
                await i.response.defer()
                await self.next_step(i)
                
            async def no_cb(i: discord.Interaction):
                await i.response.defer()
                await self.prompt_create(i, role_name)
                
            btn_yes.callback = yes_cb
            btn_no.callback = no_cb
            
            self.add_item(btn_yes)
            self.add_item(btn_no)
            
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)
        else:
            await self.prompt_create(interaction, role_name)

    async def prompt_create(self, interaction: discord.Interaction, role_name: str):
        self.clear_items()
        embed = discord.Embed(title=f"Role Setup: {role_name}", description=f"I couldn't find a matching Discord role for **{role_name}**.\nShould I create it for you?", color=discord.Color.red())
        
        btn_create = discord.ui.Button(label="Yes, Create It", style=discord.ButtonStyle.green)
        btn_skip = discord.ui.Button(label="Skip", style=discord.ButtonStyle.secondary)
        
        async def create_cb(i: discord.Interaction):
            await i.response.defer()
            try:
                new_role = await i.guild.create_role(name=role_name, hoist=True)
                await self.save_role_to_db(role_name, new_role.name, new_role.id)
            except discord.Forbidden:
                await i.followup.send("I lack permissions to create roles! Skipping...", ephemeral=True)
            self.current_idx += 1
            await self.next_step(i)
            
        async def skip_cb(i: discord.Interaction):
            await i.response.defer()
            # Save as stub (id=0)
            await self.save_role_to_db(role_name, role_name, 0)
            self.current_idx += 1
            await self.next_step(i)
            
        btn_create.callback = create_cb
        btn_skip.callback = skip_cb
        self.add_item(btn_create)
        self.add_item(btn_skip)
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def handle_manual_step(self, interaction: discord.Interaction, role_name: str):
        embed = discord.Embed(title=f"Role Setup: {role_name}", description=f"Please select the Discord role that corresponds to the game role **{role_name}**.", color=discord.Color.purple())
        
        select_menu = discord.ui.RoleSelect(placeholder="Choose a role...", min_values=1, max_values=1)
        btn_skip = discord.ui.Button(label="Skip", style=discord.ButtonStyle.secondary, row=1)
        
        async def select_cb(i: discord.Interaction):
            selected_role = select_menu.values[0]
            await self.save_role_to_db(role_name, selected_role.name, selected_role.id)
            self.current_idx += 1
            await i.response.defer()
            await self.next_step(i)
            
        async def skip_cb(i: discord.Interaction):
            await self.save_role_to_db(role_name, role_name, 0)
            self.current_idx += 1
            await i.response.defer()
            await self.next_step(i)
            
        select_menu.callback = select_cb
        btn_skip.callback = skip_cb
        
        self.add_item(select_menu)
        self.add_item(btn_skip)
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)


class Admin(Cog):
    def __init__(self, bot: My_Bot):
        self.bot = bot

    admin_group = app_commands.Group(name="admin", description="Admin & Setup commands")

    @admin_group.command(name="setup", description="Run the server setup wizard to initialize the bot.")
    async def setup_wizard(self, interaction: discord.Interaction):
        if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only the Server Owner or an Administrator can run the setup wizard.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        view = SetupWizard(interaction)
        await view.start()


async def setup(bot: My_Bot):
    await bot.add_cog(Admin(bot))
