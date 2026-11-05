from sqlalchemy import JSON, Boolean, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Channel(Base):
    __tablename__ = "channels"
    name_bot = Column(String, primary_key=True)
    id = Column(Integer)
    name_guild = Column(String)
    private = Column(Boolean)


class Role(Base):
    __tablename__ = "roles"
    name_bot = Column(String, primary_key=True)
    id = Column(Integer)
    name_guild = Column(String)
    synonyms = Column(JSON)
    team = Column(String)


class Player(Base):
    __tablename__ = "players"
    PlayerId = Column(Integer, primary_key=True)
    PlayerName = Column(String)
    PlayedGamesComplete = Column(Integer, default=0)
    WonGamesComplete = Column(Integer, default=0)
    PlayedGamesSeason = Column(Integer, default=0)
    WonGamesSeason = Column(Integer, default=0)
    Elo = Column(Integer, default=1300)
    Titles = Column(JSON)
    Achivments = Column(JSON)
    WinsPerRole = Column(JSON)


class League(Base):
    __tablename__ = "leagues"
    LeagueName = Column(String, primary_key=True)
    LowestElo = Column(Integer)
    HighestElo = Column(Integer)


class GameCadre(Base):
    __tablename__ = "game_cadre"
    cadre_type = Column(String, primary_key=True)
    data = Column(JSON)


class Lobby(Base):
    __tablename__ = "lobbies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    gamemaster_id = Column(Integer)
    cadre_type = Column(String)  # Selected standard cadre, e.g. '10er'
    status = Column(String, default="setup")  # setup, playing, finished
    phase = Column(String, default="none")  # e.g., night, day, voting
    is_active = Column(Boolean, default=True)


class LobbyPlayer(Base):
    __tablename__ = "lobby_players"
    lobby_id = Column(Integer, primary_key=True)
    player_id = Column(Integer, primary_key=True)
    role = Column(String, nullable=True)
    is_dead = Column(Boolean, default=False)


class PhaseMusic(Base):
    __tablename__ = "phase_music"
    id = Column(Integer, primary_key=True, autoincrement=True)
    phase = Column(String)  # e.g. 'NIGHT', 'DAY', 'WEREWOLVES'
    url = Column(String)
    order_idx = Column(Integer, default=0)


class ActionRequest(Base):
    __tablename__ = "action_requests"
    id = Column(Integer, primary_key=True, autoincrement=True)
    lobby_id = Column(Integer)
    player_id = Column(Integer)
    action_type = Column(String)
    target_id = Column(Integer)
    status = Column(String, default="pending")  # pending, approved, rejected
