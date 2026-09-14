from discord import app_commands
from discord.ext import commands

from lib.db.db import getRoleID


def is_gamemaster():
    async def predicate(ctx):
        if ctx.guild and ctx.guild.owner_id == ctx.author.id:
            return True
        try:
            gm_role_id = await getRoleID("gamemaster")
            return any(role.id == gm_role_id for role in ctx.author.roles)
        except ValueError:
            return False

    return commands.check(predicate)


def app_is_gamemaster():
    async def predicate(interaction):
        if interaction.guild and interaction.guild.owner_id == interaction.user.id:
            return True
        try:
            gm_role_id = await getRoleID("gamemaster")
            return any(role.id == gm_role_id for role in interaction.user.roles)
        except ValueError:
            return False

    return app_commands.check(predicate)
