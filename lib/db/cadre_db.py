import json

from sqlalchemy import select

from lib.db import db
from lib.db.models import GameCadre


async def get_cadre(cadre_type: str, guild=None) -> dict:
    async with db.AsyncSessionLocal() as session:
        result = await session.execute(
            select(GameCadre).where(GameCadre.cadre_type == cadre_type)
        )
        cadre = result.scalar_one_or_none()
        if cadre and cadre.data:
            return (
                cadre.data if isinstance(cadre.data, dict) else json.loads(cadre.data)
            )
        return {}


async def set_cadre(cadre_type: str, data: dict):
    async with db.AsyncSessionLocal() as session:
        result = await session.execute(
            select(GameCadre).where(GameCadre.cadre_type == cadre_type)
        )
        cadre = result.scalar_one_or_none()

        if cadre:
            cadre.data = data
        else:
            new_cadre = GameCadre(cadre_type=cadre_type, data=data)
            session.add(new_cadre)
        await session.commit()


async def getCadre(guild=None) -> dict:
    playing = await get_cadre("playing", guild)
    if playing:
        return playing
    return await get_cadre("default", guild)


async def setDefaultCadre(cadre: dict):
    await set_cadre("default", cadre)
    return True


async def setPlayingCadre(cadre: dict):
    await set_cadre("playing", cadre)
    return True


async def getCurrentGameCadre(guild=None) -> dict:
    return await get_cadre("currentgame", guild)


async def setCurrentGameCadre(cadre: dict):
    await set_cadre("currentgame", cadre)
    return True
