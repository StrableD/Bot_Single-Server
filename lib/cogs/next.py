from discord.ext import commands
from discord.ext.commands import Cog, Context
from lib.bot import My_Bot
from lib.helper.constants import TIMINGS
from lib.helper.errors import NoPerms
from lib.db.db import getRoleID
from lib.db.cadre_db import getCurrentGameCadre
from lib.helper.checks import is_gamemaster

class Next(Cog):
    """
    Das Modul, welches weitere Unterstützung des Spielleiters bringt.
    """

    def __init__(self, bot: My_Bot):
        self.bot = bot
        self.current_phase_index = 0
        self.night_roles = []

    async def build_night_order(self):
        cadre = await getCurrentGameCadre(self.bot.guild)
        roles_in_game = set(player_info["role"].lower() for player_info in cadre.values() if not player_info["dead"])
        
        ordered_roles = []
        for role, timing in TIMINGS.items():
            # timing is (nacht, durchgehend, abhängig)
            if timing[0] != -1:
                # Basic check if role is in game (would need real game logic for dependencies)
                if role in roles_in_game:
                    ordered_roles.append((role, timing[0]))
        
        ordered_roles.sort(key=lambda x: x[1])
        self.night_roles = [r[0] for r in ordered_roles]
        self.current_phase_index = 0

    @commands.hybrid_command(name="next_phase")
    @is_gamemaster()
    async def next_phase(self, ctx: Context):
        """
        Geht zur nächsten Nacht-Phase über und kündigt die nächste Rolle an.
        """
        if not self.night_roles:
            await self.build_night_order()
            
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
