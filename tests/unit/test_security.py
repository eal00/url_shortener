import jwt

from src.config import settings
from src.security import create_access_token, hash_password, verify_password


def test_hash_password():
    password = "testpassword123"
    hashed = hash_password(password)
    assert hashed != password
    assert hashed.startswith("$2b$")


def test_verify_password():
    password = "testpassword123"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_create_access_token():
    data = {"sub": "123"}
    token = create_access_token(data)

    decoded = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    assert decoded["sub"] == "123"
    assert "exp" in decoded
