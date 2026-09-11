from discord.ext import commands
from discord.ext.commands import Cog, Context
from lib.bot import My_Bot
from lib.helper.constants import TIMINGS, getRoleID
from lib.helper.errors import NoPerms
from lib.db.cadre_db import getCurrentGameCadre

class Next(Cog):
    """
    Das Modul, welches weitere Unterstützung des Spielleiters bringt.
    """

    def __init__(self, bot: My_Bot):
        self.bot = bot
        self.current_phase_index = 0
        self.night_roles = []

    def build_night_order(self):
        cadre = getCurrentGameCadre(self.bot.guild)
        roles_in_game = set(player_info["role"].lower() for player_info in cadre.values() if not player_info["dead"])
        
        ordered_roles = []
        for role, timing in TIMINGS.items():
            # timing is (nacht, durchgehend, abhängig)
            # We want roles that wake up at night
            if role in roles_in_game and timing[0] in (1, 2):
                ordered_roles.append(role)
        
        self.night_roles = ordered_roles
        self.current_phase_index = 0

    @commands.hybrid_command(name="next_phase")
    @commands.has_role(getRoleID("gamemaster"))
    async def next_phase(self, ctx: Context):
        """
        Geht zur nächsten Nacht-Phase über und kündigt die nächste Rolle an.
        """
        if not self.night_roles:
            self.build_night_order()
            
        if not self.night_roles:
            await ctx.send("Keine Rollen in dieser Nacht aktiv.", ephemeral=True)
            return
            
        if self.current_phase_index >= len(self.night_roles):
            await ctx.send("Die Nacht ist vorbei. Die Sonne geht auf!", delete_after=30.0)
            self.current_phase_index = 0
            return
            
        role = self.night_roles[self.current_phase_index]
        self.current_phase_index += 1
        await ctx.send(f"Spielleiter: **{role.capitalize()}**, erwache und öffne deine Augen!")

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("next")

async def setup(bot: My_Bot):
    await bot.add_cog(Next(bot))
