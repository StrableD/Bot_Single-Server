"""
Gibt Zugriff auf die Konstanten für den Bot.
"""

from json import load
import json
from os import chmod, scandir
from os.path import abspath
from pathlib import PurePath
from sqlite3 import connect
from typing import Union

from discord import Member
from discord.ext.commands.converter import RoleConverter
from discord.ext.commands.errors import CheckFailure, RoleNotFound

BOTPATH = abspath(PurePath(__file__).parents[2])

with open(BOTPATH + "/data/auth.json", "r") as jsonfile:
    DBPASSWORD = load(jsonfile).get("password")

jsonfile = open(BOTPATH + "/data/auth.json", "r")
TOKEN: str = load(jsonfile).get("token")
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
chmod(BOTPATH + "/data/db", 755)
MYDB = connect(DBPATH, check_same_thread=False)


class MyRoleConverter(RoleConverter):
    async def convert(self, ctx, argument):
        try:
            return await super.convert(ctx, argument)
        except RoleNotFound:
            for row in MYDB.execute("SELECT name_bot, synonyms FROM roles"):
                synonymList = [row[0]].extend(row[1])
                if str(argument).lower() in synonymList:
                    roleID = MYDB.execute(
                        "SELECT id FROM roles WHERE name_bot = ?", (synonymList[0],)
                    ).fetchone()[0]
                    return await super.convert(ctx, roleID)
            raise RoleNotFound


class InputError(Exception):
    pass


class ParameterError(InputError):
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

COGS = [
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

BONI = {}


def getCadre() -> dict[str, int]:
    with open(BOTPATH + "/data/cadres.json", "r") as cadreFile:
        cadres = json.load(cadreFile)
    if cadres["playing"] == {}:
        return cadres["default"]
    else:
        return cadres["playing"]


def setDefaultCadre(cadre: dict):
    with open(BOTPATH + "/data/cadres.json", "r") as cadreFile:
        currentCadres = json.load(cadreFile)
    currentCadres["default"] = cadre
    with open(BOTPATH + "/data/cadres.json", "w") as cadreFile:
        json.dump(currentCadres, cadreFile)
    return True


def setPlayingCadre(cadre: dict):
    with open(BOTPATH + "/data/cadres.json", "r") as cadreFile:
        currentCadres = json.load(cadreFile)
    currentCadres["playing"] = cadre
    with open(BOTPATH + "/data/cadres.json", "w") as cadreFile:
        json.dump(currentCadres, cadreFile)
    return True


def getCurrentGameCadre() -> dict[Member, dict[str, Union[bool, str]]]:
    """
    Hier wird der derzeitige Spielekader zurückgegeben.
    Gespeichert sind:
    Spieler: `Member`, Role: `str`, tot: `bool`, Hauptmann: `bool`, Liebespaar: `bool`
    """
    with open(BOTPATH + "/data/cadres.json", "r") as cadreFile:
        cadres = json.load(cadreFile)
    return cadres["currentgame"]


def setCurrentGameCadre(cadre: dict):
    with open(BOTPATH + "/data/cadres.json", "r") as cadreFile:
        currentCadres = json.load(cadreFile)
    currentCadres["currentgame"] = cadre
    with open(BOTPATH + "/data/cadres.json", "w") as cadreFile:
        json.dump(currentCadres, cadreFile)
    return True