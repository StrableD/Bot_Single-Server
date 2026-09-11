from discord.ext.commands.converter import RoleConverter
from discord.ext.commands.errors import RoleNotFound
import json
from lib.db.db import MYDB

class MyRoleConverter(RoleConverter):
    async def convert(self, ctx, *argument):
        argument = " ".join(argument)
        try:
            return await super().convert(ctx, argument)
        except RoleNotFound:
            for row in MYDB.execute("SELECT name_bot, synonyms FROM roles"):
                synonymList = [row[0]]
                if row[1] is not None:
                    synonymList.extend(json.loads(row[1]))
                if str(argument).lower() in synonymList:
                    roleID = MYDB.execute(
                        "SELECT id FROM roles WHERE name_bot = ?", (synonymList[0],)
                    ).fetchone()[0]
                    return await super().convert(ctx, str(roleID))
            raise RoleNotFound
