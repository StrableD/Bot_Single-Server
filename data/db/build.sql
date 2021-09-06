--Verschiedene Infos zu den Kanälen einer Guilde (ids)
CREATE TABLE IF NOT EXISTS channels (
    name_bot text PRIMARY KEY,
    id integer,
    name_guild text,
    private boolean
);
--Infos zu den Rollen (ids)
CREATE TABLE IF NOT EXISTS roles (
    name_bot text PRIMARY KEY,
    id integer,
    name_guild text,
    synonyms text, --json-list
    team text
);
--Die Spielerdatenbank
CREATE TABLE IF NOT EXISTS players (
    PlayerName text PRIMARY KEY,
    PlayerId integer,
    PlayedGamesComplete integer DEFAULT 0,
    WonGamesComplete integer DEFAULT 0,
    PlayedGamesSeason integer DEFAULT 0,
    WonGamesSeason integer DEFAULT 0,
    Elo integer,
    RankedRest text, --json-list[(json-dict,int)]
    Titles text, --json-list[str]
    Achivments text, --json-list[str]
    WinsPerRole text --json-dict[str,int]
);
--Die Ligen
CREATE TABLE IF NOT EXISTS leagues (
    LeagueName text PRIMARY KEY,
    LowestElo integer,
    HighestElo integer
);