import json
from os.path import isfile
from sqlite3.dbapi2 import DataError, DatabaseError

from discord import Member
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from lib.helper.constants import BUILDPATH, MYDB, MemberJsonDecoder, member_to_json

cursor = MYDB.cursor()

def commit():
    MYDB.commit()


def with_commit(func):
    def inner(*args, **kwargs):
        res = func(*args, **kwargs)
        commit()
        return res

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
    if type(key[1]) == str:
        cmd = f"SELECT {','.join(columns)} FROM {table} WHERE {key[0]} = '{key[1]}';"
    else:
        cmd = f"SELECT {','.join(columns)} FROM {table} WHERE {key[0]} = {key[1]};"
    cursor.execute(cmd)
    return cursor.fetchone()

# setzt die gegebenen infos in der tabelle
@with_commit
def setData(table: str, colums: tuple[str], values: tuple, condition: str = None):
    try:
        if condition == None:
            cmd = f"INSERT INTO {table} {colums} VALUES {values};"
            cursor.execute(cmd)
        else:
            zipped = tuple(zip(colums, values))
            concated = map(lambda x: f'{x[0]} = {x[1]}', zipped)
            cmd = f"UPDATE {table} SET {','.join(concated)} WHERE {condition};"
            cursor.execute(cmd)
    except:
        return False
    else:
        return True

def getChannelID(bot_name: str)->int:
    data = getData("channels", ("id",), ("name_bot", bot_name))
    if data == None or type(data[0]) != int:
        raise DataError
    elif len(data) != 1 :
        raise DatabaseError
    else:
        return data[0]

def getRoleID(bot_name: str)->int:
    data = getData("roles", ("id",), ("name_bot", bot_name))
    if data == None or type(data[0]) != int:
        raise DataError
    elif len(data) != 1 :
        raise DatabaseError
    else:
        return data[0]

def getRoleTeam(bot_name: str)->str:
    data = getData("roles", ("team",), ("name_bot", bot_name))
    if data == None or type(data[0]) != str:
        raise DataError
    elif len(data) != 1 :
        raise DatabaseError
    else:
        return data[0]

def getElo(player_id: int):
    data = getData("players", ("Elo",), ("PlayerID", player_id))
    if data == None:
        return bool(None)
    elif type(data[0]) != int:
        raise DataError
    elif len(data) != 1 :
        raise DatabaseError
    else:
        return int(data[0])

def setPlayerElo(player_id: int, new_elo: int):
    dataSet = setData("players", ("Elo",), (new_elo,), f"PlayerID = {player_id}")
    if not dataSet:
        raise DataError("Could not set the PlayerElo")

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

def saveCurrentGame(gameCadre: dict, winner: str):
    eloDict = {}
    for member in gameCadre:
        eloDict[member] = getElo(member)
    
    jsonGameCadre = json.dumps(member_to_json(gameCadre))
    jsonEloDict = json.dumps(member_to_json(eloDict))
    
    setData("games", ("GameDict", "EloDict", "winner"), (jsonGameCadre, jsonEloDict, winner))
    return cursor.lastrowid

def getUnevaluatedGames():
    cursor.execute("SELECT GameNumber FROM games WHERE evaluated = 0")
    gameNums = map(lambda x: x[0], cursor.fetchall())
    sortedgameNums = sorted(gameNums)
    return sortedgameNums

def getGameToEvaluate(gameNum: int):
    returnedTuple = getData("games", ("GameDict", "EloDict", "winner", "evaluated"), ("GameNumber", gameNum))
    if not bool(returnedTuple):
        raise DataError("No such data in the database")
    gameDict, eloDict, winner, evaluated = returnedTuple 
    if evaluated:
        raise DataError("The game was already evaluated") 
    gameDict: dict = json.loads(gameDict, cls = MemberJsonDecoder)
    eloDict: dict = json.loads(eloDict, cls=MemberJsonDecoder)
    for member, elo in eloDict.items():
        gameDict[member]["elo"] = elo
    gameDict["winner"] = winner
    return gameDict

def setGameToIsEvaluate(gameNum: int):
    return setData("games", ("evaluated",), (1,), f"GameNumber = {gameNum}")