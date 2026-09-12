import discord
from discord.ext import commands
from discord.ext.commands import Cog, Context
from discord.ui import View, Button, Select
from lib.bot import My_Bot
from lib.db.cadre_db import getCadre
from lib.db.db import getRoleID

class LobbyView(View):
    def __init__(self, gm_member, cadre):
        super().__init__(timeout=None)
        self.gm_member = gm_member
        self.cadre = cadre
        self.players = []
        self.waitlist = []
        self.max_players = sum(cadre.values()) if cadre else 0

    def generate_embed(self):
        embed = discord.Embed(title="🐺 Werewolf Game Lobby", description=f"Hosted by {self.gm_member.mention}", color=discord.Color.gold())
        embed.add_field(name=f"Players ({len(self.players)}/{self.max_players})", value="\\n".join([p.display_name for p in self.players]) or "None yet", inline=False)
        if self.waitlist:
            embed.add_field(name=f"Waitlist", value="\\n".join([p.display_name for p in self.waitlist]), inline=False)
        return embed

    @discord.ui.button(label="Join Game", style=discord.ButtonStyle.success, custom_id="lobby_join")
    async def join_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user in self.players:
            await interaction.response.send_message("You are already in the lobby!", ephemeral=True)
            return
            
        if len(self.players) >= self.max_players:
            if interaction.user not in self.waitlist:
                self.waitlist.append(interaction.user)
                await interaction.response.send_message("Lobby is full! You have been added to the waitlist.", ephemeral=True)
                await interaction.message.edit(embed=self.generate_embed())
            else:
                await interaction.response.send_message("You are already on the waitlist.", ephemeral=True)
        else:
            self.players.append(interaction.user)
            await interaction.response.send_message("You joined the game!", ephemeral=True)
            await interaction.message.edit(embed=self.generate_embed())

    @discord.ui.button(label="Start Game (GM Only)", style=discord.ButtonStyle.primary, custom_id="lobby_start")
    async def start_btn(self, interaction: discord.Interaction, button: Button):
        gm_role_id = await getRoleID("gamemaster")
        if not any(r.id == gm_role_id for r in interaction.user.roles):
            await interaction.response.send_message("Only the Gamemaster can start the game.", ephemeral=True)
            return

        if len(self.players) != self.max_players:
            await interaction.response.send_message("Cannot start until the lobby is full! Adjust the cadre if needed.", ephemeral=True)
            return

        await interaction.response.send_message(f"Starting game with {len(self.players)} players!")
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        
        # We would invoke the `startGame` logic here.
        game_cog = interaction.client.get_cog("Game")
        if game_cog:
            pass # Hook to start the game natively with self.players


class LobbyCog(Cog):
    def __init__(self, bot: My_Bot):
        self.bot = bot

    @commands.hybrid_command(name="open_lobby")
    async def open_lobby(self, ctx: Context):
        """Opens a dynamic lobby for players to join."""
        gm_role_id = await getRoleID("gamemaster")
        if not any(role.id == gm_role_id for role in ctx.author.roles):
            await ctx.send("You do not have permission to open a lobby.", ephemeral=True)
            return

        cadre = await getCadre(ctx.guild)
        view = LobbyView(ctx.author, cadre)
        await ctx.send(embed=view.generate_embed(), view=view)

async def setup(bot: My_Bot):
    await bot.add_cog(LobbyCog(bot))
