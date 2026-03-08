import asyncio
import logging

from redis.asyncio import Redis

from src.database import get_db_pool, get_redis

logger = logging.getLogger(__name__)


async def run_background_tasks():
    while True:
        try:
            redis: Redis = get_redis()

            # 1. Синхронизируем клики из Redis в БД
            updates = []
            async for key in redis.scan_iter("clicks:*"):
                short_code = key.split(":")[1]
                clicks = await redis.getdel(key)
                if clicks:
                    updates.append((int(clicks), short_code))

            pool = get_db_pool()
            async with pool.acquire() as conn:
                if updates:
                    await conn.executemany(
                        "UPDATE links SET clicks = clicks + $1, last_used_at = CURRENT_TIMESTAMP WHERE short_code = $2",
                        updates,
                    )

                # 2. Очищаем истекшие ссылки
                expired_links = await conn.fetch(
                    "DELETE FROM links WHERE expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP RETURNING short_code"
                )
                for row in expired_links:
                    await redis.delete(f"link:{row['short_code']}")

        except Exception as e:
            logger.error(f"Ошибка в фоновых задачах: {e}")

        await asyncio.sleep(60)
