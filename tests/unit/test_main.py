import pytest
from fastapi import FastAPI

from src.database import get_db_pool
from src.main import app, lifespan


@pytest.mark.asyncio
async def test_lifespan_initializes_and_closes():
    test_app = FastAPI()

    async with lifespan(test_app):
        pool = get_db_pool()
        assert not pool.is_closing()

        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            assert result == 1

    pool_after = get_db_pool()
    assert pool_after is None or pool_after.is_closing()


def test_app_configuration():
    assert app.title == "URL shortener"
    assert len(app.routes) > 0
    assert any(route.path == "/" for route in app.routes)
    assert len(app.router.routes) >= 3
