from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from sqlalchemy import delete

from lib.cogs.game import Game
from lib.db.models import Lobby


@pytest.fixture
def mock_bot():
    return MagicMock()


@pytest.fixture
def mock_interaction():
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.user.id = 12345
    interaction.user.display_name = "GM User"
    interaction.guild.owner_id = 12345
    interaction.guild.get_member = MagicMock(return_value=AsyncMock())

    mock_role = MagicMock()
    mock_role.id = 999
    interaction.user.roles = [mock_role]

    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_gm_phase_transitions_game(mock_bot, mock_interaction, setup_test_db):
    async with setup_test_db() as session:
        await session.execute(delete(Lobby))
        # Create playing lobby
        lobby = Lobby(
            is_active=True,
            status="playing",
            gamemaster_id=12345,
            cadre_type="test",
            phase="setup",
        )
        session.add(lobby)
        await session.commit()
        lobby_id = lobby.id

    game_cog = Game(mock_bot)

    # Phase is a Choice object
    phase_choice = MagicMock()
    phase_choice.name = "Night"
    phase_choice.value = "night"

    await game_cog.gm_phase.callback(game_cog, mock_interaction, phase=phase_choice)

    mock_interaction.response.send_message.assert_called_once()

    async with setup_test_db() as session:
        updated_lobby = await session.get(Lobby, lobby_id)
        assert updated_lobby.phase == "night"


@pytest.mark.asyncio
async def test_gm_phase_fails_if_no_active_game(
    mock_bot, mock_interaction, setup_test_db
):
    async with setup_test_db() as session:
        await session.execute(delete(Lobby))
        await session.commit()

    game_cog = Game(mock_bot)

    phase_choice = MagicMock()
    phase_choice.name = "Day"
    phase_choice.value = "day"

    await game_cog.gm_phase.callback(game_cog, mock_interaction, phase=phase_choice)

    args, kwargs = mock_interaction.response.send_message.call_args
    assert "No active game" in args[0]
