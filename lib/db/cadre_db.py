import json
import sqlite3
from typing import Union
from lib.db.db import MYDB, with_commit
from lib.helper.utils import member_to_json, MemberJsonDecoder

def get_cadre(cadre_type: str, guild=None) -> dict:
    row = MYDB.execute("SELECT data FROM game_cadre WHERE cadre_type = ?", (cadre_type,)).fetchone()
    if row:
        decoder = MemberJsonDecoder(guild=guild)
        return decoder.decode(row[0])
    return {}

@with_commit
def set_cadre(cadre_type: str, data: dict):
    MYDB.execute("INSERT OR REPLACE INTO game_cadre (cadre_type, data) VALUES (?, ?)", (cadre_type, json.dumps(member_to_json(data))))

def getCadre(guild=None) -> dict:
    playing = get_cadre("playing", guild)
    if playing:
        return playing
    return get_cadre("default", guild)

def setDefaultCadre(cadre: dict):
    set_cadre("default", cadre)
    return True

def setPlayingCadre(cadre: dict):
    set_cadre("playing", cadre)
    return True

def getCurrentGameCadre(guild=None) -> dict:
    return get_cadre("currentgame", guild)

def setCurrentGameCadre(cadre: dict):
    set_cadre("currentgame", cadre)
    return True
