from discord.ext.commands import Cog
from lib.bot import My_Bot

class Next(Cog):
    """
    Das Modul, welches weitere Unterstützung des Spielleiters bringt.
    """
    def __init__(self, bot: My_Bot):
        self.bot = bot
    

def setup(bot: My_Bot):
    bot.add_cog(Next(bot))