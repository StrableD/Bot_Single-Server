from sqlalchemy import Column, Integer, String, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Channel(Base):
    __tablename__ = 'channels'
    name_bot = Column(String, primary_key=True)
    id = Column(Integer)
    name_guild = Column(String)
    private = Column(Boolean)

class Role(Base):
    __tablename__ = 'roles'
    name_bot = Column(String, primary_key=True)
    id = Column(Integer)
    name_guild = Column(String)
    synonyms = Column(JSON)
    team = Column(String)

class Player(Base):
    __tablename__ = 'players'
    PlayerName = Column(String, primary_key=True)
    PlayerId = Column(Integer)
    PlayedGamesComplete = Column(Integer, default=0)
    WonGamesComplete = Column(Integer, default=0)
    PlayedGamesSeason = Column(Integer, default=0)
    WonGamesSeason = Column(Integer, default=0)
    Elo = Column(Integer, default=1300)
    Titles = Column(JSON)
    Achivments = Column(JSON)
    WinsPerRole = Column(JSON)

class League(Base):
    __tablename__ = 'leagues'
    LeagueName = Column(String, primary_key=True)
    LowestElo = Column(Integer)
    HighestElo = Column(Integer)

class Game(Base):
    __tablename__ = 'games'
    GameNumber = Column(Integer, primary_key=True, autoincrement=True)
    GameDict = Column(JSON)
    EloDict = Column(JSON)
    winner = Column(String)
    evaluated = Column(Boolean, default=False)

class BotState(Base):
    __tablename__ = 'bot_state'
    key = Column(String, primary_key=True)
    value = Column(String)

class GameCadre(Base):
    __tablename__ = 'game_cadre'
    cadre_type = Column(String, primary_key=True)
    data = Column(JSON)
