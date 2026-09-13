import discord
from discord.ext import commands
from discord.ext.commands import Cog, Context
from lib.bot import My_Bot
from lib.db.cadre_db import getCurrentGameCadre

class ActionApprovalView(discord.ui.View):
    def __init__(self, action_desc, player_id):
        super().__init__(timeout=None)
        self.action_desc = action_desc
        self.player_id = player_id

    @discord.ui.button(label="Approve (Automated)", style=discord.ButtonStyle.success, custom_id="action_approve")
    async def approve_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Notify GM
        await interaction.response.send_message(f"Action approved.", ephemeral=True)
        # Notify Player
        player = interaction.guild.get_member(self.player_id)
        if player:
            await player.send(f"✅ Your action was approved by the Gamemaster! (Automated result would go here)")
        
        # Disable buttons
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Deny / Handle Manually", style=discord.ButtonStyle.danger, custom_id="action_deny")
    async def deny_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"Action denied. You can now handle it manually.", ephemeral=True)
        player = interaction.guild.get_member(self.player_id)
        if player:
            await player.send(f"❌ Your action was denied or will be handled manually by the Gamemaster.")
        
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

class PlayerActionSelect(discord.ui.Select):
    def __init__(self, target_options):
        options = [discord.SelectOption(label=opt, description=f"Select {opt}") for opt in target_options]
        super().__init__(placeholder="Select a target...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        target = self.values[0]
        # Send approval request to GM
        gm_channel = discord.utils.get(interaction.guild.text_channels, name="gamemaster")
        if gm_channel:
            action_desc = f"{interaction.user.display_name} wants to act on {target}."
            embed = discord.Embed(title="Action Approval Needed", description=action_desc, color=discord.Color.gold())
            view = ActionApprovalView(action_desc=action_desc, player_id=interaction.user.id)
            await gm_channel.send(content=f"⚠️ <@&{discord.utils.get(interaction.guild.roles, name='gamemaster').id}> Approval Needed!", embed=embed, view=view)
            
            await interaction.response.send_message(f"Action submitted for GM approval: {target}", ephemeral=True)
        else:
            await interaction.response.send_message("Gamemaster channel not found. Cannot submit action.", ephemeral=True)

class PlayerDashboardView(discord.ui.View):
    def __init__(self, bot, target_options):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(PlayerActionSelect(target_options))

    @discord.ui.button(label="Request Gamemaster", style=discord.ButtonStyle.primary, custom_id="req_gm")
    async def request_gm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gm_channel = discord.utils.get(interaction.guild.text_channels, name="gamemaster")
        if gm_channel:
            await gm_channel.send(f"🚨 **Gamemaster requested!** {interaction.user.mention} needs you in <#{interaction.channel.id}>")
            await interaction.response.send_message("Gamemaster has been pinged!", ephemeral=True)
        else:
            await interaction.response.send_message("Gamemaster channel not found.", ephemeral=True)

class RolesCog(Cog):
    def __init__(self, bot: My_Bot):
        self.bot = bot

    @commands.hybrid_command(name="role_dashboard")
    async def spawn_role_dashboard(self, ctx: Context):
        """Spawns a player's interactive role dashboard."""
        # Check cadre to see what role they are
        cadre = await getCurrentGameCadre(ctx.guild)
        if not cadre or ctx.author not in cadre:
            await ctx.send("You do not have an active role in the current game.", ephemeral=True)
            return

        role_info = cadre[ctx.author]
        role_name = role_info["role"]
        
        # Get targets (all living players)
        targets = [member.display_name for member, info in cadre.items() if not info["dead"] and member != ctx.author]
        if not targets:
            targets = ["No valid targets"]

        embed = discord.Embed(title=f"Role: {role_name.capitalize()}", description="Use your abilities here.", color=discord.Color.purple())
        view = PlayerDashboardView(self.bot, targets[:25]) # Limit to 25 due to Discord select menu limits
        
        await ctx.send(embed=embed, view=view)

async def setup(bot: My_Bot):
    await bot.add_cog(RolesCog(bot))
