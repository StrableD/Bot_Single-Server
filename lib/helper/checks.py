from discord.ext import commands

from lib.db.db import getRoleID


def is_gamemaster():
    async def predicate(ctx):
        # Allow server owner to bypass gamemaster check (crucial for setup/recovery)
        if ctx.guild and ctx.guild.owner_id == ctx.author.id:
            return True

        try:
            gm_role_id = await getRoleID("gamemaster")
            return any(role.id == gm_role_id for role in ctx.author.roles)
        except ValueError:
            # Gamemaster role not in DB yet (bot not setup)
            return False

    return commands.check(predicate)
