import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import lib.db.db
from lib.db.models import Base


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(monkeypatch):
    # Use in-memory SQLite for tests
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    TestingSessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Patch the production sessionmaker with the testing one
    monkeypatch.setattr(lib.db.db, "AsyncSessionLocal", TestingSessionLocal)
    monkeypatch.setattr(lib.db.db, "engine", engine)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield TestingSessionLocal

    # Teardown
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
