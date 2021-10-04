from discord.ext.commands import Cog
from lib.bot import My_Bot

class Music(Cog):
    """
    Das Modul, welches die Musikunterstützung zu dem Bot hinzufügt.
    """
    def __init__(self, bot: My_Bot):
        self.bot = bot

def setup(bot: My_Bot):
    bot.add_cog(Music(bot))