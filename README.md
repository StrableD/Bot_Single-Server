# Bot_Beta_Single-Server

This is a bot for a discord server of a friend where we play werewolf. It's assisting the gamemaster to manage the game better.
It is open source and written in Python using discord.py 2.x.

No guarantee this bot works as it should.

The only language supported is currently german.

LG the developer [@StrableD](https://www.github.com/StrableD)

## Features

- **Game Cadre Management**: Set up the game cadre for the current round (which roles are included).
- **In-Game Roles**: Automatically assign roles to players and move them into the corresponding voice channel.
- **Night Phase Manager**: Automatically announce who wakes up at night in the right order using `/next_phase`.
- **Music**: Cached YouTube music playback for background atmosphere (using `yt-dlp` and `ffmpeg`).
- **Elo System**: Built in ranking for players!

## Deployment (Docker)

The easiest way to run this bot is via Docker Compose.

1. Clone the repository.
2. Rename `.env.example` to `.env` and fill in your Discord Bot Token and Guild IDs.
3. Run `docker-compose up -d --build`.

Data (like the SQLite database and music cache) will be saved persistently in the `data/` volume.
Game settings (roles, timings, emojis) can be freely edited in `config/game_config.yaml`.

## Usage & Commands

The bot utilizes Discord's modern Application Commands (Slash Commands).
- **Gamemaster Commands**: Gamemasters can manage the game state with commands like `/start`, `/dead`, `/captain`, `/love`, and `/next_phase`.
- **Player Commands**: Players can use `/choose` during Role Choice mode, or check their Elo rating with `/elo`.
- **Settings**: Adjust the game cadre using `/fill`, `/minus`, `/cadre`, `/change`, and `/standardkader`.

Note: Commands that reveal sensitive state will respond as Ephemeral messages to the invoking user.
