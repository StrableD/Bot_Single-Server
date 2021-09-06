from datetime import date
import json
from os.path import isfile
from types import FunctionType
from typing import Optional, Union

from discord import Role
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from lib.bot.constants import BUILDPATH, InputError, MYDB, ParameterError

cursor = MYDB.cursor()


def filterDict(func: Optional[FunctionType], dict: dict):
    returnDict = {}
    if func == None:
        func = lambda a: bool(a)
    for x, y in dict.items():
        if func(y):
            returnDict[x] = y
    return returnDict


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
def getData(*columns, table, key: Optional[tuple]):
    if key == None:
        cursor.execute("SELECT ? FROM ?;", tuple(columns, table))
        return cursor.fetchall()
    else:
        cursor.execute(
            "SELECT ? FROM ? WHERE ? = ?;", tuple(columns, table, key[0], key[1])
        )
        return cursor.fetchall()


# setzt die gegebenen infos in der tabelle
def setData(table, *keys: Optional[list[tuple]]):
    if keys != None:
        cursor.execute(
            "INSERT INTO ?(?) VALUES (?)",
            tuple(
                table,
                tuple(map(lambda x: x[0], keys)),
                tuple(map(lambda x: x[1], keys)),
            ),
        )
        return True
    else:
        return False


def setChannels(
    name_bot: str,
    id: Optional[int] = None,
    name_guild: Optional[str] = None,
    private: Optional[bool] = None,
):
    values = filterDict({"id": id, "name_guild": name_guild, "private": private})
    if values == None:
        raise ParameterError("Es fehlen die Parameter")
    valuestr = ",".join(map(lambda x, y: f"{x}={y}", values.items()))
    print(values)
    print(valuestr)
    execstr = f"IF({name_bot} IN SELECT name_bot FROM channels, UPDATE channels SET ({valuestr}) WHERE name_bot = {name_bot}, INSERT INTO channels({','.join(values.keys())}) SET ({','.join(values.values())})"
    cursor.execute(execstr)


def setRoles(
    name_bot: str,
    id: Optional[int] = None,
    name_guild: Optional[str] = None,
    synonyms: Optional[list] = None,
    team: Optional[str] = None,
):
    values = filterDict(
        {
            "id": id,
            "name_guild": name_guild,
            "synonyms": json.dumps(synonyms),
            "team": team,
        }
    )
    if values == None:
        raise ParameterError("Es fehlen die Parameter")
    valuestr = ",".join(map(lambda x, y: f"{x}={y}", values.items()))
    execstr = f"IF({name_bot} IN SELECT name_bot FROM roles, UPDATE roles SET ({valuestr}) WHERE name_bot = {name_bot}, INSERT INTO roles({','.join(values.keys())}) SET ({','.join(values.values())})"
    cursor.execute(execstr)


def setPlayers(
    PlayerId: int,
    PlayerName: Optional[str] = None,
    PlayedGamesComplete: Optional[int] = None,
    WonGamesComplete: Optional[int] = None,
    PlayedGamesSeason: Optional[int] = None,
    WonGamesSeason: Optional[int] = None,
    Elo: Optional[int] = None,
    RankedRest: Optional[list[tuple[dict, int]]] = None,
    Titles: Optional[list[str]] = None,
    Achivments: Optional[list[str]] = None,
    WinsPerRole: Optional[dict[str, int]] = None,
):
    values = filterDict(
        {
            "PlayerName": PlayerName,
            "PlayerGamesComplete": PlayedGamesComplete,
            "WonGAmesComplete": WonGamesComplete,
            "PlayedGamesSeason": PlayedGamesSeason,
            "WonGamesSeason": WonGamesSeason,
            "Elo": Elo,
            "RankedRest": json.dumps(RankedRest),
            "Titles": json.dumps(Titles),
            "Achivments": json.dumps(Achivments),
            "WinsPerRole": json.dumps(WinsPerRole),
        }
    )
    if values == None:
        raise ParameterError("Es fehlen die Parameter")
    valuestr = ",".join(map(lambda x, y: f"{x}={y}", values.items()))
    execstr = f"IF({PlayerId} IN SELECT PlayerId FROM players, UPDATE players SET ({valuestr}) WHERE PlayerId = {PlayerId}, INSERT INTO players({','.join(values.keys())}) SET ({','.join(values.values())})"
    cursor.execute(execstr)


def setLeagues(
    LeagueName: str, LowestElo: Optional[int] = None, HighestElo: Optional[int] = None
):
    if LowestElo == None or HighestElo == None:
        raise ParameterError("Beide Parameter müssen ausgefüllt sein")
    execscript = f"IF({LeagueName} IN SELECT LeagueName FROM leagues, UPDATE leagues SET (LowestElo={LowestElo},HighestElo={HighestElo} WHERE LeagueName={LeagueName}, INSERT INTO leagues(LowestElo,HighestElo) SET ({LowestElo},{HighestElo})"
    cursor.execute(execscript)


# holt sich die id einer rolle der guilde
def getRole(name: str) -> int:
    cursor.execute("SELECT id FROM roles WHERE name_bot = ?", (name,))
    if (ids := cursor.fetchone()) != None:
        return ids[0]
    else:
        print(ids)
        raise InputError("Die Rolle gibts nicht")


def getRoleTeam(role: Union[Role, int, str]):
    if isinstance(role, Role):
        role = Role.id
    if type(role) == int:
        cursor.execute("SELECT team from roles WHERE id = ?", (role,))
        res = cursor.fetchone()
        return res[0] if res != None else None
    elif type(role) == str:
        cursor.execute("SELECT name_bot, synonyms, team FROM roles")
        for botname, synonyms, team in cursor.fetchall():
            if role == botname or role in json.load(synonyms):
                return team
        return None
    else:
        raise ValueError(f"Die Rolle {role} gibt es nicht!")


# holt sich die id eines channel der guilde
def getChannel(name: str) -> int:
    cursor.execute("SELECT id FROM channels WHERE name_bot = ?", (name,))
    res = cursor.fetchone()
    return res[0] if res != None else None


# holt sich die ligen und gibt die grenzen zurück
def getLeagues() -> dict[str, tuple]:
    returnDict = {}
    for row in cursor.execute("SELECT LeagueName,LowestElo,HighestElo FROM leagues"):
        returnDict[str(row[0])] = (int(row[1]), int(row[2]))
    return returnDict


def getElo(playerid: int) -> Optional[int]:
    cursor.execute("SELECT Elo FROM players WHERE PlayerId = ?", (playerid,))
    res = cursor.fetchone()
    return res[0] if res != None else None


def setElo(playerid: int, newElo: int):
    execStr = f"IF({playerid} IN SELECT PlayerId FROM players, UPDATE players SET Elo = {newElo} WHERE PlayerId = {playerid}, INSERT INTO players(PlayerId, Elo) SET ({playerid},{newElo})"
    cursor.execute(execStr)


def setPlayedGames(playerid: int):
    from lib.bot import bot
    cursor.execute(
        "SELECT (PlayedGamesComplete,WonGamesComplete,PlayedGamesSeason,WonGamesSeason) FROM player WHERE PlayerId = ?",
        (playerid,),
    )
    allgames, allwins, seasongames, seasonwins = cursor.fetchone()
    if date.today() <= bot._season_date and seasongames != 0:
        seasongames = seasonwins = 1
        allgames += 1
        allwins += 1
    else:
        allgames += 1
        allwins += 1
        seasongames += 1
        seasonwins += 1
    cursor.execute(
        """UPDATE players SET
                      PlayedGamesComplete = ?,
                      WonGamesComplete = ?,
                      PlayedGamesSeason = ?,
                      WonGamesSeason = ?
                      WHERE PlayerId = ?""",
        (
            allgames,
            allwins,
            seasongames,
            seasonwins,
            playerid,
        ),
    )


def setRankedRestGames(playerid: int, playerdict: dict, result: int):
    cursor.execute("SELECT RankedRest FROM players WHERE PlayerId = ?", (playerid,))
    if (res := cursor.fetchone()) == None:
        gameTuple = [(playerdict, result)]
    else:
        gameTuple = json.loads(res[0])
        gameTuple.append((playerdict, result))
    gameDump = json.dumps(gameTuple)
    cursor.execute(
        "UPDATE players SET RankedRest = ? WHERE PlayerID = ?", (gameDump, playerid)
    )
