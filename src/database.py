import asyncpg
from redis.asyncio import Redis

from src.config import settings

pool: asyncpg.Pool | None = None
redis_client: Redis | None = None


async def get_db_conn() -> asyncpg.Connection:
    async with pool.acquire() as conn:
        yield conn


def get_redis() -> Redis:
    return redis_client


def get_db_pool() -> asyncpg.Pool:
    return pool


async def init_db():
    global pool, redis_client
    pool = await asyncpg.create_pool(dsn=settings.database_url)
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)

    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS links (
                short_code VARCHAR(20) PRIMARY KEY,
                original_url TEXT NOT NULL,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                clicks INTEGER DEFAULT 0,
                expires_at TIMESTAMP WITH TIME ZONE,
                last_used_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_links_user_id ON links(user_id);
            CREATE INDEX IF NOT EXISTS idx_links_original_url ON links(original_url);
        """)


async def close_db():
    await pool.close()
    await redis_client.aclose()
