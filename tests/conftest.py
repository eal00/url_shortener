import os
import sys

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Добавляем src в PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.database import close_db, get_db_pool, get_redis, init_db
from src.main import app


@pytest_asyncio.fixture(autouse=True)
async def db_setup_teardown():
    await init_db()
    pool = get_db_pool()
    redis = get_redis()

    # Очистка таблиц перед тестом
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE users CASCADE")
        await conn.execute("TRUNCATE TABLE links CASCADE")

    # Очистка Redis перед тестом
    await redis.flushdb()

    yield

    await close_db()


@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
