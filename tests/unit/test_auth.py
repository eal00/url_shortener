import jwt
import pytest
from fastapi import HTTPException

from src.auth import _decode_token, get_current_user_id, get_optional_user_id
from src.config import settings


@pytest.mark.asyncio
async def test_auth_dependencies():
    # Тестируем get_current_user_id с неверным токеном
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id("invalid_token")
    assert exc_info.value.status_code == 401

    # Тестируем get_current_user_id с токеном без sub
    token_no_sub = jwt.encode({"other": "data"}, settings.secret_key, algorithm=settings.algorithm)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(token_no_sub)
    assert exc_info.value.status_code == 401

    # Тестируем get_optional_user_id с неверным токеном
    with pytest.raises(HTTPException) as exc_info:
        await get_optional_user_id("invalid_token")
    assert exc_info.value.status_code == 401

    # Тестируем get_optional_user_id с токеном без sub
    with pytest.raises(HTTPException) as exc_info:
        await get_optional_user_id(token_no_sub)
    assert exc_info.value.status_code == 401

    # Тестируем get_optional_user_id с None токеном
    result = await get_optional_user_id(None)
    assert result is None


@pytest.mark.asyncio
async def test_decode_token_errors():
    # Тестируем с истекшим токеном
    expired_token = jwt.encode({"sub": "1", "exp": 0}, settings.secret_key, algorithm=settings.algorithm)
    with pytest.raises(HTTPException) as exc_info:
        _decode_token(expired_token)
    assert exc_info.value.status_code == 401

    # Тестируем с неверным ключом
    wrong_key_token = jwt.encode({"sub": "1"}, "wrong_key", algorithm=settings.algorithm)
    with pytest.raises(HTTPException) as exc_info:
        _decode_token(wrong_key_token)
    assert exc_info.value.status_code == 401

    # Тестируем с неверным форматом токена
    with pytest.raises(HTTPException) as exc_info:
        _decode_token("not.a.token")
    assert exc_info.value.status_code == 401
