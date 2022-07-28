"""
Gibt Zugriff auf die Konstanten für den Bot.
"""

import json
import logging
from os import scandir
from os.path import abspath
from pathlib import PurePath
import re
from sqlite3 import connect
from typing import Union

from discord.member import Member
from discord.ext.commands.converter import RoleConverter
from discord.ext.commands.errors import CheckFailure, RoleNotFound

BOTPATH = abspath(PurePath(__file__).parents[2])

with open(BOTPATH + "/data/auth.0", "r", encoding="utf-8") as jsonfile:
    DBPASSWORD = json.load(jsonfile).get("password")

jsonfile = open(BOTPATH + "/data/auth.0", "r", encoding="utf-8")
TOKEN: str = json.load(jsonfile).get("token")
jsonfile.close()
del jsonfile

CHRONICLE_PATTERN = """{datum} - Runde {numRound}

Max. Spieler: {maxPlayer}
Spieler: {numPlayer}
Spielleitung: {gamemaster}

{playerDict}

Liebespaar: {lovebird}
Gewinner: {winner}"""

DBPATH = BOTPATH + "/data/db/database.db"
BUILDPATH = BOTPATH + "/data/db/build.sql"
MYDB = connect(DBPATH, check_same_thread=False)


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


class LogFilter(logging.Filter):

    def filter(self, record: logging.LogRecord):
        if re.search(r"(^Add.* job)|(Scheduler started)|(^Running job)|(Job .* executed successfully)", record.msg):
            return False
        return True


class InputError(Exception):
    pass


class NoPerms(CheckFailure):
    def __init__(self, message):
        self.message = ",".join(message) if type(message) != str else message
        super().__init__(self.message)


ALL_ROLES = [
    "Werwolf-1",
    "Werwolf-2",
    "Polarwolf",
    "Wolfsseher",
    "Werwolfjunges",
    "Weißer-Werwolf",
    "Werschweinchen",
    "Jason",
    "Jäger",
    "Hexe",
    "Seherin",
    "Amor",
    "Dorfdepp",
    "Rotkäppchen",
    "Geschwister-1",
    "Geschwister-2",
    "Geschwister-3",
    "Geschwister-4",
    "Dorfbewohner-1",
    "Dorfbewohner-2",
    "Dorfbewohner-3",
    "Der-Rabe",
    "tot",
    "Hauptmann",
    "Spielleiter",
]

COGS: list[str] = [
    cog.name.split(".")[0] for cog in scandir(BOTPATH + "/lib/cogs/") if cog.name != "__pycache__"
]

EMOJIS = {
    0: "0️⃣",
    1: "1️⃣",
    2: "2️⃣",
    3: "3️⃣",
    4: "4️⃣",
    5: "5️⃣",
    6: "6️⃣",
    7: "7️⃣",
    8: "8️⃣",
    9: "9️⃣",
    10: "🔟",
}

TIMINGS = {
    # "role": (nacht,durchgehend,abhängig vom einsetzen der fähigkeit)
    "amor": (1, False, False),
    "polarwolf": (1, True, False),
    "seherin": (1, True, False),
    "werwolf": (1, True, False),
    "wolfseher": (1, True, False),
    "weiser-werwolf": (2, True, True),
    "hexe": (1, True, False),
    "geschwister": (2, True, False),
    "der-rabe": (1, True, False),
}

ROLEAURA = {
    "normal": ["dorfbewohner", "amor", "rotkäppchen", "geschwister", "dorfdepp"],
    "special": ["hexe", "jäger", "seherin", "werschweinchen", "der-rabe"],
}

BONI = {"weißer-werwolf": 0.5,
        "lovebirds": 0.4,
        "dorfbewohner": 0.35,
        "amor": 0.35,
        "jäger": 0.3,
        "werschweinchen": 0.25,
        "der-rabe": 0.25,
        "jason": 0.25,
        "dorfdepp": 0.25,
        "werwolf": 0.2,
        "geschwister": 0.15,
        "werwolfjunges": 0.15,
        "rotkäppchen": 0.1,
        "polarwolf": 0.1,
        "hexe": 0.1,
        "wolfseher": 0.1,
        "seherin": 0.05
        }


class MyGuild:
    def __init__(self):
        self._guild = None

    @property
    def guild(self):
        return self._guild

    @guild.setter
    def guild(self, guild):
        self._guild = guild


myGuild = MyGuild()


def member_to_json(json_dict):
    def lookForMember(jsonDict):
        org_dict = jsonDict.copy()
        for key, value in org_dict.items():
            if type(value) == dict:
                jsonDict[key] = lookForMember(value)
            if type(key) == Member:
                res = jsonDict.pop(key)
                key = f"<MemberID={key.id}>"
                jsonDict[key] = res
            elif type(value) == Member:
                jsonDict[key] = f"<MemberID={value.id}>"
        return jsonDict

    return lookForMember(json_dict)


class MemberJsonDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)

    def lookForMember(self, jsonDict):
        org_dict = jsonDict.copy()
        for key, value in org_dict.items():
            if type(value) == dict:
                jsonDict[key] = self.lookForMember(value)
            if str(key).startswith("<MemberID="):
                res = jsonDict.pop(key)
                key = myGuild.guild.get_member(int(key.strip("<>").split("=")[1]))
                jsonDict[key] = res
            elif str(value).startswith("<MemberID="):
                jsonDict[key] = myGuild.guild.get_member(int(key.strip("<>").split("=")[1]))
        return jsonDict

    def object_hook(self, json_dict):
        return self.lookForMember(json_dict)


def getCadre() -> dict[str, int]:
    with open(BOTPATH + "/data/cadres.json", "r") as cadreFile:
        cadres = json.load(cadreFile, cls=MemberJsonDecoder)
    if cadres["playing"] == {}:
        return cadres["default"]
    else:
        return cadres["playing"]


def setDefaultCadre(cadre: dict):
    with open(BOTPATH + "/data/cadres.json", "r") as cadreFile:
        currentCadres = json.load(cadreFile, cls=MemberJsonDecoder)
    currentCadres["default"] = cadre
    dumpCadre = member_to_json(currentCadres)
    with open(BOTPATH + "/data/cadres.json", "w") as cadreFile:
        cadreFile.write(json.dumps(dumpCadre))
    return True


def setPlayingCadre(cadre: dict):
    with open(BOTPATH + "/data/cadres.json", "r") as cadreFile:
        currentCadres = json.load(cadreFile, cls=MemberJsonDecoder)
    currentCadres["playing"] = cadre
    dumpCadre = member_to_json(currentCadres)
    with open(BOTPATH + "/data/cadres.json", "w") as cadreFile:
        cadreFile.write(json.dumps(dumpCadre))
    return True


def getCurrentGameCadre() -> dict[Member, dict[str, Union[bool, str]]]:
    """
    Hier wird der derzeitige Spielekader zurückgegeben.
    Gespeichert sind:
    Spieler: `Member`, Role: `str`, tot: `bool`, Hauptmann: `bool`, Liebespaar: `bool`
    """
    with open(BOTPATH + "/data/cadres.json", "r") as cadreFile:
        cadres = json.load(cadreFile, cls=MemberJsonDecoder)
    return cadres["currentgame"]


def setCurrentGameCadre(cadre: dict):
    with open(BOTPATH + "/data/cadres.json", "r") as cadreFile:
        currentCadres = json.load(cadreFile, cls=MemberJsonDecoder)
    currentCadres["currentgame"] = cadre
    dumpCadre = member_to_json(currentCadres)
    with open(BOTPATH + "/data/cadres.json", "w") as cadreFile:
        cadreFile.write(json.dumps(dumpCadre))
    return True
