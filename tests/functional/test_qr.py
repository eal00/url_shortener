import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_qr_code_success(async_client: AsyncClient):
    # Создаем тестовую ссылку
    link_payload = {"original_url": "https://example.com/qr-test", "custom_alias": "qrtest1"}
    await async_client.post("/links/shorten", json=link_payload)

    # Запрашиваем QR-код
    response = await async_client.get("/links/qrtest1/qr")

    # Проверяем успешный статус
    assert response.status_code == 200

    # Проверяем правильный тип контента (PNG)
    assert response.headers["content-type"] == "image/png"

    # Проверяем, что вернулись какие-то бинарные данные (сигнатура PNG)
    content = response.content
    assert content.startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_get_qr_code_not_found(async_client: AsyncClient):
    # Запрашиваем QR-код для несуществующей ссылки
    response = await async_client.get("/links/nonexistent123/qr")

    assert response.status_code == 404
