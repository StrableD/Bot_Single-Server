# Bot_Beta_Single-Server

This is a bot for a discord server of a friend where we play werewolf. It's assisting the gamemaster to manage the game better.
It is open source and written in Python using discord.py 2.x.

No guarantee this bot works as it should.

The only language supported is currently german.

LG the developer [@StrableD](https://www.github.com/StrableD)

## Features

- **Game Cadre Management**: Set up the game cadre for the current round (which roles are included).
- **Interactive Match Lobby**: Gamemasters can spin up a lobby via `/gm start` where players can natively join through Discord UI buttons.
- **Action Request System**: Players queue role actions targeting each other directly via `/game action`, allowing the Gamemaster to review and approve them transparently.
- **Setup Wizard**: Fully interactive setup wizard using `/admin setup` to cleanly provision secret ("DBVM???") roles and public roles securely across the server.
- **Music**: Cached YouTube music playback for background atmosphere (using `yt-dlp` and `ffmpeg`).
- **Elo System**: Built-in ranking for players!

## Deployment (Docker)

The easiest way to run this bot is via Docker Compose.

1. Clone the repository.
2. Rename `.env.example` to `.env` and fill in your Discord Bot Token, Guild IDs, and Owner ID.
3. Run `docker-compose up -d --build`.

Data (like the SQLite database and music cache) will be saved persistently in the `data/` volume.
Game settings (e.g. roles) can be edited in `config/game_config.yaml`.

## Usage & Commands

The bot utilizes Discord's modern Application Commands (Slash Commands).
- **Gamemaster Commands**: Gamemasters can manage the game state with commands like `/gm start`, `/gm stop`, and `/gm phase`.
- **Player Commands**: Players can check their Elo rating with `/elo`, view the current cadre with `/game current_cadre`, and submit actions via `/game action`.
- **Settings**: Adjust the game cadre using `/cadre change` and `/cadre standardkader`.

Note: Commands that reveal sensitive state will respond as Ephemeral messages to the invoking user.
