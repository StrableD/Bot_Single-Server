import pytest
from lib.db.models import Lobby, LobbyPlayer, PhaseMusic
from sqlalchemy import select

@pytest.mark.asyncio
async def test_lobby_creation(setup_test_db):
    async with setup_test_db() as session:
        # Create a Lobby
        lobby = Lobby(gamemaster_id=12345, cadre_type="standard", is_active=True)
        session.add(lobby)
        await session.commit()
        
        assert lobby.id is not None
        
        # Add LobbyPlayers
        lp1 = LobbyPlayer(lobby_id=lobby.id, player_id=111)
        lp2 = LobbyPlayer(lobby_id=lobby.id, player_id=222)
        session.add_all([lp1, lp2])
        await session.commit()
        
        # Verify LobbyPlayers
        result = await session.execute(select(LobbyPlayer).where(LobbyPlayer.lobby_id == lobby.id))
        players = result.scalars().all()
        assert len(players) == 2
        assert {p.player_id for p in players} == {111, 222}

@pytest.mark.asyncio
async def test_phase_music(setup_test_db):
    async with setup_test_db() as session:
        # Create PhaseMusic bindings
        pm1 = PhaseMusic(phase="NIGHT", url="https://youtube.com/night", order_idx=0)
        pm2 = PhaseMusic(phase="NIGHT", url="https://youtube.com/night2", order_idx=1)
        pm3 = PhaseMusic(phase="DAY", url="https://youtube.com/day", order_idx=0)
        session.add_all([pm1, pm2, pm3])
        await session.commit()
        
        # Query NIGHT phase music
        result = await session.execute(select(PhaseMusic).where(PhaseMusic.phase == "NIGHT").order_by(PhaseMusic.order_idx))
        night_music = result.scalars().all()
        
        assert len(night_music) == 2
        assert night_music[0].url == "https://youtube.com/night"
        assert night_music[1].url == "https://youtube.com/night2"
