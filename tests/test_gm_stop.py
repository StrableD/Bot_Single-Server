from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from sqlalchemy import delete, select

from lib.cogs.game import Game
from lib.db.models import Lobby, LobbyPlayer, Player


@pytest.fixture
def mock_bot():
    bot = MagicMock()
    return bot


@pytest.fixture
def mock_interaction():
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.user.id = 12345
    interaction.user.display_name = "GM User"
    interaction.guild.owner_id = 12345

    mock_role = MagicMock()
    mock_role.id = 999
    interaction.user.roles = [mock_role]

    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_gm_stop_no_active_lobby(mock_bot, mock_interaction, setup_test_db):
    async with setup_test_db() as session:
        await session.execute(delete(Lobby))
        await session.commit()

    game_cog = Game(mock_bot)

    mock_choice = MagicMock()
    mock_choice.value = "dorf"
    mock_choice.name = "Dorf"

    await game_cog.gm_stop.callback(game_cog, mock_interaction, mock_choice)

    mock_interaction.followup.send.assert_called_with(
        "There is no active game lobby to stop.", ephemeral=True
    )


@pytest.mark.asyncio
async def test_gm_stop_awards_elo(mock_bot, mock_interaction, setup_test_db):
    async with setup_test_db() as session:
        await session.execute(delete(Lobby))
        await session.execute(delete(LobbyPlayer))
        await session.execute(delete(Player))

        lobby = Lobby(is_active=True, gamemaster_id=12345, cadre_type="test")
        session.add(lobby)
        await session.flush()

        winner_player = Player(
            PlayerId=1,
            PlayerName="P1",
            Elo=1300,
            PlayedGamesComplete=0,
            WonGamesComplete=0,
        )
        session.add(winner_player)
        lp1 = LobbyPlayer(lobby_id=lobby.id, player_id=1, role="Dorfbewohner")
        session.add(lp1)

        loser_player = Player(
            PlayerId=2,
            PlayerName="P2",
            Elo=1300,
            PlayedGamesComplete=0,
            WonGamesComplete=0,
        )
        session.add(loser_player)
        lp2 = LobbyPlayer(lobby_id=lobby.id, player_id=2, role="Werwolf-1")
        session.add(lp2)

        await session.commit()

    game_cog = Game(mock_bot)
    mock_choice = MagicMock()
    mock_choice.value = "dorf"
    mock_choice.name = "Dorf"

    await game_cog.gm_stop.callback(game_cog, mock_interaction, mock_choice)

    mock_interaction.followup.send.assert_called_with(
        "Game stopped. Winner: Dorf. Elo calculated.", ephemeral=False
    )

    async with setup_test_db() as session:
        p1 = await session.get(Player, 1)
        assert p1.PlayedGamesComplete == 1
        assert p1.WonGamesComplete == 1
        assert p1.Elo > 1300

        p2 = await session.get(Player, 2)
        assert p2.PlayedGamesComplete == 1
        assert p2.WonGamesComplete == 0
        assert p2.Elo < 1300

        # Verify lobby is closed
        res = await session.execute(select(Lobby).where(Lobby.is_active))
        active_lobby = res.scalar_one_or_none()
        assert active_lobby is None
