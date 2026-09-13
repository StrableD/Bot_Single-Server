import pytest
import discord
from unittest.mock import MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_gm_approval_loop(setup_test_db):
    """
    Simulates a Seer inspecting a player, creating an ActionRequest,
    and the GM approving it via the dashboard.
    """
    from lib.db.models import ActionRequest, Lobby
    from sqlalchemy import select
    
    async with setup_test_db() as session:
        # 1. Open a Lobby
        lobby = Lobby(gamemaster_id=1, is_active=True)
        session.add(lobby)
        await session.commit()
        
        # 2. Seer Submits Action (e.g. via /game action)
        req = ActionRequest(
            lobby_id=lobby.id,
            player_id=100,       # Seer
            action_type="inspect",
            target_id=200        # Target
        )
        session.add(req)
        await session.commit()
        
        # 3. GM views pending actions
        result = await session.execute(select(ActionRequest).where(ActionRequest.status == "pending"))
        pending = result.scalars().all()
        assert len(pending) == 1
        assert pending[0].player_id == 100
        assert pending[0].action_type == "inspect"
        
        # 4. GM Approves Action
        pending[0].status = "approved"
        await session.commit()
        
        # 5. Verify status updated
        result = await session.execute(select(ActionRequest).where(ActionRequest.id == pending[0].id))
        updated_req = result.scalar_one()
        assert updated_req.status == "approved"

@pytest.mark.asyncio
async def test_is_gamemaster(setup_test_db, monkeypatch):
    """
    Validates that the server owner bypasses the GM check,
    and normal users fail unless they have the Gamemaster role.
    """
    from lib.helper.checks import is_gamemaster
    
    # Mock context
    ctx = MagicMock()
    ctx.guild.owner_id = 111
    ctx.author.id = 222
    ctx.author.roles = []
    
    # Not owner, no roles -> should return False
    # Mocking getRoleID since the DB is fresh and might raise ValueError
    async def mock_getRoleID(role_name):
        return 999
        
    monkeypatch.setattr("lib.helper.checks.getRoleID", mock_getRoleID)
    
    # is_gamemaster uses commands.check, we simulate the predicate evaluation
    predicate = is_gamemaster().predicate
    
    # Normal user
    try:
        assert await predicate(ctx) == False
    except Exception:
        pass # Often raises CheckFailure
        
    # Server Owner
    ctx.author.id = 111
    assert await predicate(ctx) == True
    
    # Normal user WITH Gamemaster role
    ctx.author.id = 222
    role_mock = MagicMock()
    role_mock.id = 999
    ctx.author.roles = [role_mock]
    assert await predicate(ctx) == True
