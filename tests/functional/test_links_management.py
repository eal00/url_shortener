import asyncio
import json
from datetime import datetime

import pytest
from httpx import AsyncClient

from src.background_tasks import run_background_tasks
from src.database import get_redis


@pytest.mark.asyncio
async def test_update_link(async_client: AsyncClient):
    # Регистрируемся и логинимся
    payload_user = {"username": "updatetest", "password": "password123"}
    await async_client.post("/auth/register", json=payload_user)
    login_resp = await async_client.post("/auth/login", data=payload_user)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Создаем ссылку
    link_payload = {"original_url": "https://example.com/old", "custom_alias": "upd1"}
    await async_client.post("/links/shorten", json=link_payload, headers=headers)

    # Обновляем ссылку
    update_payload = {"original_url": "https://example.com/new"}
    update_resp = await async_client.put("/links/upd1", json=update_payload, headers=headers)

    assert update_resp.status_code == 200
    assert update_resp.json()["original_url"] == "https://example.com/new"

    # Проверяем, что редирект теперь на новый URL
    redir_resp = await async_client.get("/upd1", follow_redirects=False)
    assert redir_resp.status_code == 307
    assert redir_resp.headers["location"] == "https://example.com/new"


@pytest.mark.asyncio
async def test_delete_link(async_client: AsyncClient):
    # Регистрируемся и логинимся
    payload_user = {"username": "deltest", "password": "password123"}
    await async_client.post("/auth/register", json=payload_user)
    login_resp = await async_client.post("/auth/login", data=payload_user)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Создаем ссылку
    link_payload = {"original_url": "https://example.com/del", "custom_alias": "del1"}
    await async_client.post("/links/shorten", json=link_payload, headers=headers)

    # Удаляем ссылку
    del_resp = await async_client.delete("/links/del1", headers=headers)
    assert del_resp.status_code == 200

    # Проверяем, что редирект больше не работает
    redir_resp = await async_client.get("/del1", follow_redirects=False)
    assert redir_resp.status_code == 404


@pytest.mark.asyncio
async def test_link_stats(async_client: AsyncClient, mocker):
    # Регистрируемся и логинимся
    payload_user = {"username": "statstest", "password": "password123"}
    await async_client.post("/auth/register", json=payload_user)
    login_resp = await async_client.post("/auth/login", data=payload_user)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Создаем ссылку
    link_payload = {"original_url": "https://example.com/stats", "custom_alias": "stat1"}
    await async_client.post("/links/shorten", json=link_payload, headers=headers)

    # Делаем переход
    await async_client.get("/stat1", follow_redirects=False)

    # Мокаем бесконечный цикл, чтобы run_background_tasks выполнился один раз и вышел
    mocker.patch("asyncio.sleep", side_effect=asyncio.CancelledError)
    try:
        await run_background_tasks()
    except asyncio.CancelledError:
        pass

    stats_resp = await async_client.get("/links/stat1/stats", headers=headers)
    assert stats_resp.status_code == 200

    data = stats_resp.json()
    assert data["clicks"] == 1
    assert data["original_url"] == "https://example.com/stats"

    datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
    datetime.fromisoformat(data["last_used_at"].replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_unauthorized_access(async_client: AsyncClient):
    # Создаем ссылку без авторизации (анонимную)
    link_payload = {"original_url": "https://example.com/anon", "custom_alias": "anon1"}
    await async_client.post("/links/shorten", json=link_payload)

    # Регистрируем пользователя
    payload_user = {"username": "stranger", "password": "password123"}
    await async_client.post("/auth/register", json=payload_user)
    login_resp = await async_client.post("/auth/login", data=payload_user)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Чужой пользователь пытается удалить или обновить анонимную ссылку
    del_resp = await async_client.delete("/links/anon1", headers=headers)
    assert del_resp.status_code == 404

    upd_resp = await async_client.put("/links/anon1", json={"original_url": "https://example.com/123"}, headers=headers)
    assert upd_resp.status_code == 404

    stats_resp = await async_client.get("/links/anon1/stats", headers=headers)
    assert stats_resp.status_code == 404


@pytest.mark.asyncio
async def test_link_errors(async_client: AsyncClient, mocker):
    # Регистрируемся и логинимся
    payload_user = {"username": "errortest", "password": "password123"}
    await async_client.post("/auth/register", json=payload_user)
    login_resp = await async_client.post("/auth/login", data=payload_user)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 404 for search, update, delete, stats
    resp = await async_client.get("/links/search?original_url=https://nonexistent.com", headers=headers)
    assert resp.status_code == 404

    resp = await async_client.put("/links/nonexistent", json={"original_url": "https://example.com"}, headers=headers)
    assert resp.status_code == 404

    resp = await async_client.delete("/links/nonexistent", headers=headers)
    assert resp.status_code == 404

    resp = await async_client.get("/links/nonexistent/stats", headers=headers)
    assert resp.status_code == 404

    # 400 for duplicate custom_alias
    link_payload = {"original_url": "https://example.com/dup", "custom_alias": "dup_alias"}
    await async_client.post("/links/shorten", json=link_payload, headers=headers)
    resp = await async_client.post("/links/shorten", json=link_payload, headers=headers)
    assert resp.status_code == 400

    # 500 when unable to generate unique short_code
    mocker.patch("src.links.generate_short_code", return_value="dup_alias")
    resp = await async_client.post("/links/shorten", json={"original_url": "https://example.com"}, headers=headers)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_update_link_invalidates_cache(async_client: AsyncClient):
    payload_user = {"username": "cacheuser", "password": "password123"}
    await async_client.post("/auth/register", json=payload_user)
    login_resp = await async_client.post("/auth/login", data=payload_user)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    link_payload = {"original_url": "https://example.com/old", "custom_alias": "cacheupd"}
    await async_client.post("/links/shorten", json=link_payload, headers=headers)

    redis = get_redis()
    await redis.delete("link:cacheupd")

    await async_client.get("/cacheupd", follow_redirects=False)

    cached = await redis.get("link:cacheupd")
    assert cached is not None

    cached_data = json.loads(cached)
    assert cached_data["original_url"] == "https://example.com/old"

    update_payload = {"original_url": "https://example.com/new"}
    await async_client.put("/links/cacheupd", json=update_payload, headers=headers)

    cached_after = await redis.get("link:cacheupd")
    assert cached_after is None

    resp = await async_client.get("/cacheupd", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "https://example.com/new"


@pytest.mark.asyncio
async def test_delete_link_invalidates_cache(async_client: AsyncClient):
    payload_user = {"username": "cachedel", "password": "password123"}
    await async_client.post("/auth/register", json=payload_user)
    login_resp = await async_client.post("/auth/login", data=payload_user)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    link_payload = {"original_url": "https://example.com/del", "custom_alias": "cachedel"}
    await async_client.post("/links/shorten", json=link_payload, headers=headers)

    await async_client.get("/cachedel", follow_redirects=False)

    redis = get_redis()
    cached = await redis.get("link:cachedel")
    assert cached is not None

    cached_data = json.loads(cached)
    assert "original_url" in cached_data

    await async_client.delete("/links/cachedel", headers=headers)

    cached_after = await redis.get("link:cachedel")
    assert cached_after is None


@pytest.mark.asyncio
async def test_unauthorized_access_other_user_link(async_client: AsyncClient):
    payload_user1 = {"username": "user1", "password": "password123"}
    await async_client.post("/auth/register", json=payload_user1)
    login_resp1 = await async_client.post("/auth/login", data=payload_user1)
    token1 = login_resp1.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    link_payload = {"original_url": "https://example.com/user1", "custom_alias": "user1link"}
    await async_client.post("/links/shorten", json=link_payload, headers=headers1)

    payload_user2 = {"username": "user2", "password": "password123"}
    await async_client.post("/auth/register", json=payload_user2)
    login_resp2 = await async_client.post("/auth/login", data=payload_user2)
    token2 = login_resp2.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    del_resp = await async_client.delete("/links/user1link", headers=headers2)
    assert del_resp.status_code == 404

    upd_resp = await async_client.put("/links/user1link", json={"original_url": "https://example.com/hacked"}, headers=headers2)
    assert upd_resp.status_code == 404

    stats_resp = await async_client.get("/links/user1link/stats", headers=headers2)
    assert stats_resp.status_code == 404
