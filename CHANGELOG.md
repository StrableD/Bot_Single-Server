# Changelog

## v2.0.0 (Beta - V2 Overhaul)
- **Database Architecture Migration:** Fully migrated from flat JSON and legacy SQLite queries to a robust, asynchronous `SQLAlchemy` ORM structure (`aiosqlite`).
- **Slash Commands Migration:** Completely rewrote the bot to natively use Discord App Commands (`discord.app_commands`) instead of the outdated prefix command system.
- **Action Queue System:** Replaced messy legacy state management with a dynamic database-backed Action Request Queue (Lobby -> Roles -> Actions).
- **Interactive Match Lobby:** Replaced text-based joining with native Discord UI Views and Buttons via the new `/gm start` lobby system.
- **Setup Wizard Rewrite:** Rewrote `/admin setup` to efficiently provision secret roles natively (preventing manual role leakage) through an automated workflow.
- **Codebase Cleanups & Modernization:** 
  - Purged hundreds of lines of obsolete v1 logic (e.g. `member_to_json`, dead `Elo` calculation blocks, Reaction-based surveys, `APScheduler`).
  - Implemented strict linting and automatic formatting via `ruff` checks inside the Docker container.
  - Rewrote polling to utilize `discord.ui.Select` dropdowns rather than uploading Custom Server Emojis dynamically.

## v1.1.1
- New approach for the database interaction.
- New database functions.
- New command `calcAllElo`.

## v1.1.0
- New command `reset`.
- Attributes of the bot are saved regularly.
- Minor changes in elo cog.

## v1.0.1
- Problems regarding the `chronicle` command fixed.
- New hidden command `setGamemaster`.

## v1.0.0
- New command `ghostvoices`.
- New command `defaultCadre`.
- New command `elo`.
- Removed command `exit`.
- Ranking system is integrated.
- Database is usable.
- Several commands got revised.
- The appearance of the messages has been changed.
