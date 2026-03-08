import io
import random
import string
from typing import Any

import asyncpg
import qrcode
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import AnyHttpUrl
from redis.asyncio import Redis

from src.auth import get_current_user_id, get_optional_user_id
from src.config import settings
from src.database import get_db_conn, get_redis
from src.schemas import LinkCreate, LinkListItem, LinkResponse, LinksListResponse, LinkStats, LinkUpdate, get_short_url

router = APIRouter(prefix="/links", tags=["links"])


def generate_short_code() -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(settings.short_code_length))


@router.post("/shorten", response_model=LinkResponse)
async def shorten_link(
    link_data: LinkCreate,
    user_id: int | None = Depends(get_optional_user_id),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> Any:
    """
    Создание короткой ссылки.
    Помимо original_url, можно передать custom_alias для задания своей ссылки и expires_at для указания времени жизни.
    По умолчанию expires_at устанавливается на месяц вперед от текущей даты.
    Доступно как для авторизованных, так и для анонимных пользователей.
    """
    for _ in range(1 if link_data.custom_alias else 10):
        short_code = link_data.custom_alias or generate_short_code()
        try:
            await conn.execute(
                """
                INSERT INTO links (short_code, original_url, user_id, expires_at)
                VALUES ($1, $2, $3, $4)
                """,
                short_code,
                str(link_data.original_url),
                user_id,
                link_data.expires_at,
            )
            break
        except asyncpg.UniqueViolationError:
            if link_data.custom_alias:
                raise HTTPException(status_code=400, detail="Custom alias already exists")
    else:
        raise HTTPException(status_code=500, detail="Could not generate unique short code")

    return LinkResponse(
        short_code=short_code,
        original_url=str(link_data.original_url),
        expires_at=link_data.expires_at,
    )


@router.get("", response_model=LinksListResponse)
async def list_links(
    user_id: int = Depends(get_current_user_id),
    conn: asyncpg.Connection = Depends(get_db_conn),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> Any:
    """
    Список всех ссылок текущего пользователя с пагинацией.
    """
    offset = (page - 1) * per_page
    rows = await conn.fetch(
        """
        SELECT short_code, original_url, clicks, created_at, last_used_at, expires_at
        FROM links
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        user_id,
        per_page,
        offset,
    )
    total = await conn.fetchval("SELECT COUNT(*) FROM links WHERE user_id = $1", user_id)

    return LinksListResponse(
        links=[LinkListItem(**dict(row)) for row in rows],
        total=total or 0,
        page=page,
        per_page=per_page,
    )


@router.get("/search", response_model=LinkResponse)
async def search_link(
    original_url: AnyHttpUrl,
    user_id: int = Depends(get_current_user_id),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> Any:
    """
    Поиск короткой ссылки по original_url.
    Поиск осуществляется только среди ссылок текущего авторизованного пользователя.
    """
    row = await conn.fetchrow(
        "SELECT short_code, original_url, expires_at FROM links WHERE original_url = $1 AND user_id = $2 LIMIT 1",
        str(original_url),
        user_id,
    )

    if not row:
        raise HTTPException(status_code=404, detail="Link not found")

    return LinkResponse(
        short_code=row["short_code"],
        original_url=row["original_url"],
        expires_at=row["expires_at"],
    )


@router.put("/{short_code}", response_model=LinkResponse)
async def update_link(
    short_code: str,
    link_update: LinkUpdate,
    user_id: int = Depends(get_current_user_id),
    conn: asyncpg.Connection = Depends(get_db_conn),
    redis: Redis = Depends(get_redis),
) -> Any:
    """
    Изменение оригинального URL для ранее созданной короткой ссылки.
    Доступно только автору ссылки. Время жизни не изменяется.
    """
    row = await conn.fetchrow(
        """
        UPDATE links
        SET original_url = $1
        WHERE short_code = $2 AND user_id = $3
        RETURNING expires_at
        """,
        str(link_update.original_url),
        short_code,
        user_id,
    )

    if not row:
        raise HTTPException(status_code=404, detail="Link not found")

    await redis.delete(f"link:{short_code}")

    return LinkResponse(
        short_code=short_code,
        original_url=str(link_update.original_url),
        expires_at=row["expires_at"],
    )


@router.delete("/{short_code}")
async def delete_link(
    short_code: str,
    user_id: int = Depends(get_current_user_id),
    conn: asyncpg.Connection = Depends(get_db_conn),
    redis: Redis = Depends(get_redis),
) -> Any:
    """
    Удаление короткой ссылки по её short_code.
    Доступно только автору ссылки.
    """
    res = await conn.execute("DELETE FROM links WHERE short_code = $1 AND user_id = $2", short_code, user_id)
    if res == "DELETE 0":
        raise HTTPException(status_code=404, detail="Link not found")

    await redis.delete(f"link:{short_code}")

    return {"message": "Link deleted successfully"}


@router.get("/{short_code}/stats", response_model=LinkStats)
async def get_link_stats(
    short_code: str,
    user_id: int = Depends(get_current_user_id),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> Any:
    """
    Получение статистики по короткой ссылке (original_url, время создания, последнего использования, количество кликов).
    Доступно только автору ссылки.
    """
    row = await conn.fetchrow(
        "SELECT original_url, created_at, last_used_at, clicks FROM links WHERE short_code = $1 AND user_id = $2", short_code, user_id
    )

    if not row:
        raise HTTPException(status_code=404, detail="Link not found")

    return LinkStats(**dict(row))


def _generate_qr(full_url: str) -> io.BytesIO:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(full_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return buf


@router.get("/{short_code}/qr")
async def get_qr_code(
    short_code: str,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> Any:
    """
    Генерация и возврат QR-кода для короткой ссылки в формате PNG.
    """
    existing = await conn.fetchval("SELECT 1 FROM links WHERE short_code = $1", short_code)
    if not existing:
        raise HTTPException(status_code=404, detail="Link not found")

    full_url = get_short_url(short_code)

    buf = await run_in_threadpool(_generate_qr, full_url)

    return StreamingResponse(buf, media_type="image/png")
