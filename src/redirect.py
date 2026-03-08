import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis

from src.database import get_db_pool, get_redis

router = APIRouter(tags=["redirect"])


@router.get("/{short_code}")
async def redirect_to_original(
    short_code: str,
    redis: Redis = Depends(get_redis),
) -> Any:
    """
    Редирект по короткому коду на оригинальный URL.
    Поддерживает кэширование в Redis на 1 час и проверку срока жизни (expires_at).
    При каждом переходе обновляет статистику кликов в БД.
    """
    original_url = None
    expires_at = None

    # 1. Сначала пытаемся получить URL из кэша (Redis)
    cached_data = await redis.get(f"link:{short_code}")

    if cached_data:
        data = json.loads(cached_data)
        original_url = data["original_url"]
        expires_at_str = data.get("expires_at")
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str)
    else:
        # 2. Если в кэше нет - идем в БД
        async with get_db_pool().acquire() as conn:
            row = await conn.fetchrow(
                "SELECT original_url, expires_at FROM links WHERE short_code = $1",
                short_code,
            )

            if not row:
                raise HTTPException(status_code=404, detail="Link not found")

            original_url = row["original_url"]
            expires_at = row["expires_at"]

        await redis.setex(
            f"link:{short_code}",
            3600,
            json.dumps(
                {
                    "original_url": original_url,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                }
            ),
        )

    if expires_at and expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail="Expired link")

    # Увеличиваем счетчик кликов в Redis (таска в фоне подхватит и обновит в БД).
    # Используем Redis, чтобы избежать DDoS при частых переходах.
    await redis.incr(f"clicks:{short_code}")

    return RedirectResponse(url=original_url, status_code=307)
