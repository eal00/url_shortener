import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from src.background_tasks import run_background_tasks
from src.database import get_db_pool, get_redis


@pytest.mark.asyncio
async def test_cleanup_expired_links_logic(mocker):
    pool = get_db_pool()

    # 1. Создаем две ссылки: одну истекшую, одну валидную
    now = datetime.now(timezone.utc)
    expired_time = now - timedelta(days=1)
    valid_time = now + timedelta(days=1)

    async with pool.acquire() as conn:
        # Вставляем напрямую, чтобы избежать логики роутеров и кэшей
        await conn.execute(
            "INSERT INTO links (short_code, original_url, expires_at) VALUES ($1, $2, $3)", "exp123", "https://expired.com", expired_time
        )
        await conn.execute(
            "INSERT INTO links (short_code, original_url, expires_at) VALUES ($1, $2, $3)", "val123", "https://valid.com", valid_time
        )

    # 2. Вызываем логику очистки, прерывая бесконечный цикл через мок
    mocker.patch("asyncio.sleep", side_effect=asyncio.CancelledError)

    with pytest.raises(asyncio.CancelledError):
        await run_background_tasks()

    # 3. Проверяем, что истекшая удалена, а валидная осталась
    async with pool.acquire() as conn:
        expired_exists = await conn.fetchval("SELECT 1 FROM links WHERE short_code = $1", "exp123")
        valid_exists = await conn.fetchval("SELECT 1 FROM links WHERE short_code = $1", "val123")

        assert expired_exists is None
        assert valid_exists == 1


@pytest.mark.asyncio
async def test_cleanup_expired_links_exception(mocker):
    # Мокаем get_db_pool чтобы вызвать исключение
    mocker.patch("src.background_tasks.get_db_pool", side_effect=Exception("DB Error"))
    mocker.patch("asyncio.sleep", side_effect=asyncio.CancelledError)

    with pytest.raises(asyncio.CancelledError):
        await run_background_tasks()


@pytest.mark.asyncio
async def test_sync_clicks_from_redis(mocker):
    pool = get_db_pool()
    redis = get_redis()

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO links (short_code, original_url, clicks) VALUES ($1, $2, $3)", "clicktest", "https://clicktest.com", 0
        )

    await redis.set("clicks:clicktest", "5")

    mocker.patch("asyncio.sleep", side_effect=asyncio.CancelledError)

    with pytest.raises(asyncio.CancelledError):
        await run_background_tasks()

    async with pool.acquire() as conn:
        clicks = await conn.fetchval("SELECT clicks FROM links WHERE short_code = $1", "clicktest")
        assert clicks == 5

    cached_clicks = await redis.get("clicks:clicktest")
    assert cached_clicks is None


@pytest.mark.asyncio
async def test_cleanup_expired_removes_cache(mocker):
    pool = get_db_pool()
    redis = get_redis()

    expired_time = datetime.now(timezone.utc) - timedelta(days=1)
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO links (short_code, original_url, expires_at) VALUES ($1, $2, $3)", "expcache", "https://expcache.com", expired_time
        )

    await redis.set("link:expcache", '{"original_url": "https://expcache.com"}')

    mocker.patch("asyncio.sleep", side_effect=asyncio.CancelledError)

    with pytest.raises(asyncio.CancelledError):
        await run_background_tasks()

    async with pool.acquire() as conn:
        exists = await conn.fetchval("SELECT 1 FROM links WHERE short_code = $1", "expcache")
        assert exists is None

    cached = await redis.get("link:expcache")
    assert cached is None


@pytest.mark.asyncio
async def test_background_tasks_no_updates(mocker):
    mocker.patch("asyncio.sleep", side_effect=asyncio.CancelledError)

    with pytest.raises(asyncio.CancelledError):
        await run_background_tasks()


@pytest.mark.asyncio
async def test_background_tasks_redis_error(mocker):
    mocker.patch("src.background_tasks.get_redis", side_effect=Exception("Redis Error"))
    mocker.patch("asyncio.sleep", side_effect=asyncio.CancelledError)

    with pytest.raises(asyncio.CancelledError):
        await run_background_tasks()


@pytest.mark.asyncio
async def test_sync_clicks_with_none_value(mocker):
    pool = get_db_pool()
    redis = get_redis()

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO links (short_code, original_url, clicks) VALUES ($1, $2, $3)", "nonetest", "https://nonetest.com", 0
        )

    await redis.set("clicks:nonetest", "invalid")

    mocker.patch("asyncio.sleep", side_effect=asyncio.CancelledError)

    with pytest.raises(asyncio.CancelledError):
        await run_background_tasks()

    async with pool.acquire() as conn:
        clicks = await conn.fetchval("SELECT clicks FROM links WHERE short_code = $1", "nonetest")
        assert clicks == 0
