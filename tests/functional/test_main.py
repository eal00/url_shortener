import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_redirect(async_client: AsyncClient):
    response = await async_client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"
