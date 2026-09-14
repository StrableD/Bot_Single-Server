import asyncio
import json
from os.path import isfile, abspath
from pathlib import PurePath
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, update, delete
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from lib.db.models import Base, Channel, Role, Player, League, Game, BotState, GameCadre
from discord import Member

BOTPATH = abspath(PurePath(__file__).parents[2])
DBPATH = BOTPATH + "/data/db/database.db"

# Create async engine and sessionmaker
engine = create_async_engine(f"sqlite+aiosqlite:///{DBPATH}", echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def build():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def autosave(sched: AsyncIOScheduler):
    pass # Managed by session commits natively now, but we can leave this for backwards compat if needed

async def getChannelID(bot_name: str) -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Channel).where(Channel.name_bot == bot_name))
        channel = result.scalar_one_or_none()
        if channel:
            return channel.id
        raise ValueError(f"Channel {bot_name} not found")

async def getRoleID(bot_name: str) -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Role).where(Role.name_bot == bot_name))
        role = result.scalar_one_or_none()
        if role:
            return role.id
        raise ValueError(f"Role {bot_name} not found")

async def getRoleTeam(bot_name: str) -> str:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Role).where(Role.name_bot == bot_name))
        role = result.scalar_one_or_none()
        if role:
            return role.team
        raise ValueError(f"Role {bot_name} not found")

async def getElo(player_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Player).where(Player.PlayerId == player_id))
        player = result.scalar_one_or_none()
        return player.Elo if player else None

async def setPlayerElo(player_id: int, new_elo: int):
    async with AsyncSessionLocal() as session:
        await session.execute(update(Player).where(Player.PlayerId == player_id).values(Elo=new_elo))
        await session.commit()

async def getLeagues():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(League))
        leagues = result.scalars().all()
        return {l.LeagueName: (l.LowestElo or 0, l.HighestElo or 10000) for l in leagues}

async def resetSeason():
    async with AsyncSessionLocal() as session:
        await session.execute(update(Player).values(PlayedGamesSeason=0, WonGamesSeason=0, Elo=1300))
        await session.commit()

async def updateMembers(members: list[Member]):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Player.PlayerId))
        player_ids = set(result.scalars().all())
        
        for member in members:
            if member.id in player_ids:
                await session.execute(update(Player).where(Player.PlayerId == member.id).values(PlayerName=member.display_name))
            else:
                new_player = Player(PlayerName=member.display_name, PlayerId=member.id)
                session.add(new_player)
        await session.commit()



async def getUnevaluatedGames():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Game.GameNumber).where(Game.evaluated == False))
        return sorted(result.scalars().all())

async def getGameToEvaluate(gameNum: int, guild=None):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Game).where(Game.GameNumber == gameNum))
        game = result.scalar_one_or_none()
        if not game:
            raise ValueError("No such data in the database")
        if game.evaluated:
            raise ValueError("The game was already evaluated")
        
        decoder = MemberJsonDecoder(guild=guild)
        gameDict = decoder.decode(json.dumps(game.GameDict)) if isinstance(game.GameDict, dict) else decoder.decode(game.GameDict)
        eloDict = decoder.decode(json.dumps(game.EloDict)) if isinstance(game.EloDict, dict) else decoder.decode(game.EloDict)
        
        for member, elo in eloDict.items():
            if member in gameDict:
                gameDict[member]["elo"] = elo
        gameDict["winner"] = game.winner
        return gameDict

async def setGameToIsEvaluate(gameNum: int):
    async with AsyncSessionLocal() as session:
        await session.execute(update(Game).where(Game.GameNumber == gameNum).values(evaluated=True))
        await session.commit()
