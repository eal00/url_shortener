import json
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from src.database import get_db_pool, get_redis


@pytest.mark.asyncio
async def test_shorten_link_anonymous(async_client: AsyncClient):
    payload = {"original_url": "https://example.com/test"}
    response = await async_client.post("/links/shorten", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "short_code" in data
    assert data["original_url"] == payload["original_url"]


@pytest.mark.asyncio
async def test_shorten_link_custom_alias(async_client: AsyncClient):
    payload = {"original_url": "https://example.com/test", "custom_alias": "myalias123"}
    response = await async_client.post("/links/shorten", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["short_code"] == "myalias123"


@pytest.mark.asyncio
async def test_redirect(async_client: AsyncClient):
    payload = {"original_url": "https://example.com/redirect-target", "custom_alias": "redir1"}
    await async_client.post("/links/shorten", json=payload)

    response = await async_client.get("/redir1", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == payload["original_url"]


@pytest.mark.asyncio
async def test_redirect_expired(async_client: AsyncClient):
    past_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    payload = {"original_url": "https://example.com/exp", "custom_alias": "exp1", "expires_at": past_date}
    await async_client.post("/links/shorten", json=payload)

    response = await async_client.get("/exp1", follow_redirects=False)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_search_link(async_client: AsyncClient):
    # Регистрируемся и логинимся
    payload_user = {"username": "searchtest", "password": "password123"}
    await async_client.post("/auth/register", json=payload_user)
    login_resp = await async_client.post("/auth/login", data=payload_user)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"original_url": "https://example.com/search-target", "custom_alias": "search1"}
    await async_client.post("/links/shorten", json=payload, headers=headers)

    response = await async_client.get("/links/search?original_url=https://example.com/search-target", headers=headers)
    assert response.status_code == 200
    assert response.json()["short_code"] == "search1"


@pytest.mark.asyncio
async def test_redirect_invalid_format(async_client: AsyncClient):
    response = await async_client.get("/invalid-code-1234!!", follow_redirects=False)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_redirect_with_expiration_cached(async_client: AsyncClient):
    future = datetime.now(timezone.utc) + timedelta(days=1)

    link_payload = {"original_url": "https://example.com/cached-exp", "custom_alias": "cacheexp", "expires_at": future.isoformat()}
    await async_client.post("/links/shorten", json=link_payload)

    # Первый запрос: кэшируем ссылку с expires_at
    resp1 = await async_client.get("/cacheexp", follow_redirects=False)
    assert resp1.status_code == 307

    # Второй запрос: читаем из кэша
    resp2 = await async_client.get("/cacheexp", follow_redirects=False)
    assert resp2.status_code == 307


@pytest.mark.asyncio
async def test_redirect_without_expiration(async_client: AsyncClient):
    link_payload = {"original_url": "https://example.com/no-exp", "custom_alias": "noexp1"}
    await async_client.post("/links/shorten", json=link_payload)

    resp = await async_client.get("/noexp1", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "https://example.com/no-exp"


@pytest.mark.asyncio
async def test_redirect_cached_without_expiration(async_client: AsyncClient):
    link_payload = {"original_url": "https://example.com/cached-no-exp", "custom_alias": "cachenoexp"}
    await async_client.post("/links/shorten", json=link_payload)

    resp1 = await async_client.get("/cachenoexp", follow_redirects=False)
    assert resp1.status_code == 307

    resp2 = await async_client.get("/cachenoexp", follow_redirects=False)
    assert resp2.status_code == 307


@pytest.mark.asyncio
async def test_shorten_link_with_user_id(async_client: AsyncClient):
    payload_user = {"username": "linkuser", "password": "password123"}
    await async_client.post("/auth/register", json=payload_user)
    login_resp = await async_client.post("/auth/login", data=payload_user)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"original_url": "https://example.com/user-link"}
    response = await async_client.post("/links/shorten", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "short_code" in data
    assert "short_url" in data


@pytest.mark.asyncio
async def test_list_links(async_client: AsyncClient):
    payload_user = {"username": "listuser", "password": "password123"}
    await async_client.post("/auth/register", json=payload_user)
    login_resp = await async_client.post("/auth/login", data=payload_user)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(5):
        payload = {"original_url": f"https://example.com/link{i}", "custom_alias": f"link{i}"}
        await async_client.post("/links/shorten", json=payload, headers=headers)

    response = await async_client.get("/links", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["links"]) == 5
    assert data["page"] == 1
    assert data["per_page"] == 20
    assert all("short_url" in link for link in data["links"])


@pytest.mark.asyncio
async def test_list_links_pagination(async_client: AsyncClient):
    payload_user = {"username": "paguser", "password": "password123"}
    await async_client.post("/auth/register", json=payload_user)
    login_resp = await async_client.post("/auth/login", data=payload_user)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(25):
        payload = {"original_url": f"https://example.com/pag{i}", "custom_alias": f"pag{i}"}
        await async_client.post("/links/shorten", json=payload, headers=headers)

    response1 = await async_client.get("/links?page=1&per_page=10", headers=headers)
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["total"] == 25
    assert len(data1["links"]) == 10
    assert data1["page"] == 1
    assert data1["per_page"] == 10

    response2 = await async_client.get("/links?page=2&per_page=10", headers=headers)
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["total"] == 25
    assert len(data2["links"]) == 10
    assert data2["page"] == 2

    response3 = await async_client.get("/links?page=3&per_page=10", headers=headers)
    assert response3.status_code == 200
    data3 = response3.json()
    assert data3["total"] == 25
    assert len(data3["links"]) == 5
    assert data3["page"] == 3


@pytest.mark.asyncio
async def test_list_links_empty(async_client: AsyncClient):
    payload_user = {"username": "emptyuser", "password": "password123"}
    await async_client.post("/auth/register", json=payload_user)
    login_resp = await async_client.post("/auth/login", data=payload_user)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await async_client.get("/links", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert len(data["links"]) == 0


@pytest.mark.asyncio
async def test_link_response_short_url(async_client: AsyncClient):
    payload = {"original_url": "https://example.com/shorturl", "custom_alias": "shorturl1"}
    response = await async_client.post("/links/shorten", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "short_url" in data
    assert data["short_url"] == f"http://localhost:8000/{data['short_code']}"


@pytest.mark.asyncio
async def test_list_links_requires_auth(async_client: AsyncClient):
    response = await async_client.get("/links")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_redirect_cache_with_none_expires_at(async_client: AsyncClient):
    link_payload = {"original_url": "https://example.com/no-exp-cache", "custom_alias": "noexpcache"}
    await async_client.post("/links/shorten", json=link_payload)

    redis = get_redis()
    await redis.setex("link:noexpcache", 3600, json.dumps({"original_url": "https://example.com/no-exp-cache", "expires_at": None}))

    resp = await async_client.get("/noexpcache", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "https://example.com/no-exp-cache"


@pytest.mark.asyncio
async def test_redirect_cache_without_expires_at_key(async_client: AsyncClient):
    redis = get_redis()
    await redis.setex("link:noexpkey", 3600, json.dumps({"original_url": "https://example.com/no-exp-key"}))

    resp = await async_client.get("/noexpkey", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "https://example.com/no-exp-key"


@pytest.mark.asyncio
async def test_redirect_cache_expired_in_cache(async_client: AsyncClient):
    redis = get_redis()
    expired_time = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    await redis.setex("link:expiredcache", 3600, json.dumps({"original_url": "https://example.com/expired", "expires_at": expired_time}))

    resp = await async_client.get("/expiredcache", follow_redirects=False)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_shorten_link_with_expires_at(async_client: AsyncClient):
    future = datetime.now(timezone.utc) + timedelta(days=1)
    payload = {"original_url": "https://example.com/exp", "expires_at": future.isoformat()}
    response = await async_client.post("/links/shorten", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "short_code" in data
    expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
    assert expires_at > datetime.now(expires_at.tzinfo)


@pytest.mark.asyncio
async def test_list_links_max_per_page(async_client: AsyncClient):
    payload_user = {"username": "maxuser", "password": "password123"}
    await async_client.post("/auth/register", json=payload_user)
    login_resp = await async_client.post("/auth/login", data=payload_user)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await async_client.get("/links?per_page=100", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["per_page"] == 100


@pytest.mark.asyncio
async def test_list_links_min_per_page(async_client: AsyncClient):
    payload_user = {"username": "minuser", "password": "password123"}
    await async_client.post("/auth/register", json=payload_user)
    login_resp = await async_client.post("/auth/login", data=payload_user)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await async_client.get("/links?per_page=1", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["per_page"] == 1


@pytest.mark.asyncio
async def test_redirect_from_db_with_none_expires_at(async_client: AsyncClient):
    pool = get_db_pool()
    redis = get_redis()

    await redis.delete("link:dbnoexp")

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO links (short_code, original_url, expires_at) VALUES ($1, $2, $3)", "dbnoexp", "https://example.com/db-no-exp", None
        )

    resp = await async_client.get("/dbnoexp", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "https://example.com/db-no-exp"

    cached = await redis.get("link:dbnoexp")
    cached_data = json.loads(cached)
    assert cached_data["original_url"] == "https://example.com/db-no-exp"
    assert cached_data["expires_at"] is None
