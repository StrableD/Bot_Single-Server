from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from sqlalchemy import delete, select

from lib.cogs.game import Game, LobbyView
from lib.db.models import GameCadre, Lobby, LobbyPlayer


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
    interaction.guild.get_member = MagicMock(return_value=AsyncMock())

    mock_role = MagicMock()
    mock_role.id = 999
    interaction.user.roles = [mock_role]

    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.message = AsyncMock()
    interaction.message.embeds = [MagicMock()]
    return interaction


@pytest.mark.asyncio
async def test_gm_start_creates_lobby(mock_bot, mock_interaction, setup_test_db):
    async with setup_test_db() as session:
        await session.execute(delete(Lobby))
        await session.commit()

    game_cog = Game(mock_bot)

    await game_cog.gm_start.callback(game_cog, mock_interaction)

    async with setup_test_db() as session:
        res = await session.execute(select(Lobby).where(Lobby.is_active))
        lobby = res.scalar_one_or_none()
        assert lobby is not None
        assert lobby.gamemaster_id == 12345

    mock_interaction.response.send_message.assert_called_once()
    args, kwargs = mock_interaction.response.send_message.call_args
    assert "embed" in kwargs
    assert "view" in kwargs


@pytest.mark.asyncio
async def test_start_match_assigns_roles(mock_bot, mock_interaction, setup_test_db):
    async with setup_test_db() as session:
        await session.execute(delete(Lobby))
        await session.execute(delete(LobbyPlayer))
        await session.execute(delete(GameCadre))

        # Set playing cadre
        cadre = GameCadre(cadre_type="playing", data={"werwolf": 1, "dorfbewohner": 2})
        session.add(cadre)

        # Create active lobby
        lobby = Lobby(is_active=True, gamemaster_id=12345, cadre_type="test")
        session.add(lobby)
        await session.flush()

        # Add 3 players
        for i in range(1, 4):
            session.add(LobbyPlayer(lobby_id=lobby.id, player_id=i))

        await session.commit()
        lobby_id = lobby.id

    view = LobbyView(lobby_id=lobby_id)
    await view.start_button.callback(mock_interaction)

    async with setup_test_db() as session:
        res = await session.execute(
            select(LobbyPlayer).where(LobbyPlayer.lobby_id == lobby_id)
        )
        players = res.scalars().all()
        assert len(players) == 3

        roles = [p.role for p in players]
        assert roles.count("werwolf") == 1
        assert roles.count("dorfbewohner") == 2

        # Lobby should be marked as playing
        updated_lobby = await session.get(Lobby, lobby_id)
        assert updated_lobby.status == "playing"
        assert updated_lobby.is_active
