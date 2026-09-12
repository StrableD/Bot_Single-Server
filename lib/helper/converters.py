import json
from discord.ext.commands.converter import RoleConverter
from discord.ext.commands.errors import RoleNotFound
from lib.db.db import AsyncSessionLocal
from lib.db.models import Role
from sqlalchemy import select

class MyRoleConverter(RoleConverter):
    async def convert(self, ctx, *argument):
        argument = " ".join(argument)
        try:
            return await super().convert(ctx, argument)
        except RoleNotFound:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Role))
                roles = result.scalars().all()
                for role_record in roles:
                    synonymList = [role_record.name_bot]
                    if role_record.synonyms:
                        # Assuming synonyms is stored as a list
                        synonyms_data = role_record.synonyms if isinstance(role_record.synonyms, list) else json.loads(role_record.synonyms)
                        synonymList.extend(synonyms_data)
                    
                    if str(argument).lower() in synonymList:
                        return await super().convert(ctx, str(role_record.id))
            raise RoleNotFound
