import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user(async_client: AsyncClient):
    payload = {"username": "testuser", "password": "password123"}
    response = await async_client.post("/auth/register", json=payload)
    assert response.status_code == 200
    assert response.json() == {"message": "User created successfully"}

    # Попытка регистрации с тем же именем
    response2 = await async_client.post("/auth/register", json=payload)
    assert response2.status_code == 400


@pytest.mark.asyncio
async def test_login_user(async_client: AsyncClient):
    # Сначала регистрируем
    payload = {"username": "testuser2", "password": "password123"}
    await async_client.post("/auth/register", json=payload)

    # Теперь логинимся
    response = await async_client.post("/auth/login", data=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Попытка логина с неверным паролем
    bad_payload = {"username": "testuser2", "password": "wrongpassword"}
    bad_response = await async_client.post("/auth/login", data=bad_payload)
    assert bad_response.status_code == 401


@pytest.mark.asyncio
async def test_login_user_not_found(async_client: AsyncClient):
    payload = {"username": "nonexistent", "password": "password123"}
    response = await async_client.post("/auth/login", data=payload)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_password(async_client: AsyncClient):
    payload = {"username": "testuser3", "password": "password123"}
    await async_client.post("/auth/register", json=payload)

    wrong_payload = {"username": "testuser3", "password": "wrongpassword"}
    response = await async_client.post("/auth/login", data=wrong_payload)
    assert response.status_code == 401
