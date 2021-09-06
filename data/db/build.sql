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
    synonyms json, --json-list
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
    Elo integer DEFAULT 1300,
    RankedRest json, --json-list[(json-dict,int)]
    Titles json, --json-list[str]
    Achivments json, --json-list[str]
    WinsPerRole json --json-dict[str,int]
);
--Die Ligen
CREATE TABLE IF NOT EXISTS leagues (
    LeagueName text PRIMARY KEY,
    LowestElo integer,
    HighestElo integer
);