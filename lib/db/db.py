from datetime import date
import json
from os.path import isfile
from sqlite3.dbapi2 import DataError, DatabaseError
from types import FunctionType
from typing import Optional, Union

from discord import Role
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from lib.bot.constants import BUILDPATH, InputError, MYDB, ParameterError

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
def getData(table: str, coulums: tuple[str], key: tuple[str]):
    cmd = r"SELECT {columns} FROM {table} WHERE {key}"
    cmd = cmd.format(coulums=coulums, table=table, key= "=".join(key))
    cursor.execute(cmd)
    return cursor.fetchall()


# setzt die gegebenen infos in der tabelle
def setData(table: str, colums: tuple(str), values: tuple(str), condition: str = None):
    try:
        if not condition:
            cmd = f"INSERT INTO {table} {colums} VALUES {values}"
            cursor.execute(cmd)
        else:
            concated = map(lambda x,y: x+"="+y, zip(colums, values))
            cmd = f"UPDATE {table} SET ({','.join(concated)}) WHERE {condition}"
            cursor.execute(cmd)
    except:
        return False
    else:
        return True

def getChannelID(bot_name: str):
    data = getData("channels", ("id"), ("name_bot", bot_name))
    if len(data) != 1:
        raise DatabaseError
    elif not data[0] or not data[0].isdecimal():
        raise DataError
    else:
        return int(data[0])

def getRoleID(bot_name: str):
    data = getData("roles", ("id"), ("name_bot", bot_name))
    if len(data) != 1:
        raise DatabaseError
    elif not data[0] or not data[0].isdecimal():
        raise DataError
    else:
        return int(data[0])

def getRoleTeam(bot_name: str):
    data = getData("roles", ("team"), ("name_bot", bot_name))
    if len(data) != 1:
        raise DatabaseError
    elif not data[0] or not data[0].isdecimal():
        raise DataError
    else:
        return str(data[0])

def getElo(player_id: int):
    data = getData("players", ("Elo"), ("PlayerID", player_id))
    if len(data) != 1:
        raise DatabaseError
    elif not data[0] or not data[0].isdecimal():
        raise DataError
    else:
        return int(data[0])