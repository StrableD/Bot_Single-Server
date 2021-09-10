from os.path import isfile
from sqlite3.dbapi2 import DataError, DatabaseError

from discord import Member
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from lib.bot.constants import BUILDPATH, MYDB

cursor = MYDB.cursor()

def commit():
    MYDB.commit()


def with_commit(func):
    def inner(*args, **kwargs):
        func(*args, **kwargs)
        commit()

    return inner


# erstellt die db
@with_commit
def build():
    if isfile(BUILDPATH):
        with open(BUILDPATH, "r", encoding="utf-8") as script:
            cursor.executescript(script.read())


def autosave(sched: AsyncIOScheduler):
    sched.add_job(commit, CronTrigger(second="*/20"))


# holt sich die angeforderte infos
def getData(table: str, columns: tuple[str], key: tuple[str]):
    cmd = f"SELECT {columns} FROM {table} WHERE {key[0]} = '{key[1]}';"
    cursor.execute(cmd)
    return cursor.fetchone()

# setzt die gegebenen infos in der tabelle
@with_commit
def setData(table: str, colums: tuple[str], values: tuple, condition: str = None):
    try:
        if not condition:
            cmd = f"INSERT INTO {table} {colums} VALUES {values};"
            cursor.execute(cmd)
        else:
            concated = map(lambda x,y: x+"="+y, zip(colums, values))
            cmd = f"UPDATE {table} SET ({','.join(concated)}) WHERE {condition};"
            cursor.execute(cmd)
    except:
        return False
    else:
        return True

def getChannelID(bot_name: str)->int:
    data = getData("channels", ("id"), ("name_bot", bot_name))
    if data == None or type(data[0]) != int:
        raise DataError
    elif len(data) != 1 :
        raise DatabaseError
    else:
        return data[0]

def getRoleID(bot_name: str)->int:
    data = getData("roles", ("id"), ("name_bot", bot_name))
    if data == None or type(data[0]) != int:
        raise DataError
    elif len(data) != 1 :
        raise DatabaseError
    else:
        return data[0]

def getRoleTeam(bot_name: str)->str:
    data = getData("roles", ("team"), ("name_bot", bot_name))
    if data == None or type(data[0]) != str:
        raise DataError
    elif len(data) != 1 :
        raise DatabaseError
    else:
        return data[0]

def getElo(player_id: int)->int:
    data = getData("players", ("Elo"), ("PlayerID", player_id))
    if data == None or type(data[0]) != int:
        raise DataError
    elif len(data) != 1 :
        raise DatabaseError
    else:
        return data[0]

def setPlayerElo(player_id: int, new_elo: int):
    if not setData("players", ("Elo"), (new_elo), f"PlayerID = {player_id}"):
        raise DataError

def getLeagues():
    league_dict = {}
    for row in cursor.execute("SELECT * FROM leagues;"):
        league_dict[row[0]] = (row[1] if row[1] != None else 0, row[2] if row[2] != None else 10000)
    return league_dict

@with_commit
def resetSeason():
    cursor.execute("UPDATE players SET PlayedGamesSeason = 0, WonGamesSeason = 0, Elo = 1300;")

@with_commit
def updateMembers(members: list[Member]):
    for member in members:
        playerids = cursor.execute("SELECT PlayerID FROM players").fetchall()
        playerids = tuple(map(lambda x: x[0], playerids))
        if not bool(playerids):
            cmd = f"INSERT INTO players(PlayerName, PlayerID) VALUES {(member.display_name, member.id)};"
        elif member.id in playerids:
            cmd = f"UPDATE players SET PlayerName = '{member.display_name}' WHERE PlayerID = '{member.id}';"
        else:
            cmd = f"INSERT INTO players(PlayerName, PlayerID) VALUES {(member.display_name, member.id)};"
        cursor.execute(cmd)