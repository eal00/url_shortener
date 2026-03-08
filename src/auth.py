import asyncpg
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from src.config import settings
from src.database import get_db_conn
from src.schemas import Token, UserCreate
from src.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


@router.post("/register")
async def register(user: UserCreate, conn: asyncpg.Connection = Depends(get_db_conn)):
    """
    Регистрация нового пользователя.
    Принимает username и password, сохраняет в БД хэш пароля.
    """
    hashed_pw = await run_in_threadpool(hash_password, user.password)
    try:
        await conn.execute("INSERT INTO users (username, password_hash) VALUES ($1, $2)", user.username, hashed_pw)
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=400, detail="Username already registered")

    return {"message": "User created successfully"}


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), conn: asyncpg.Connection = Depends(get_db_conn)):
    """
    Авторизация пользователя.
    Проверяет связку username/password и в случае успеха возвращает JWT токен.
    """
    row = await conn.fetchrow("SELECT id, password_hash FROM users WHERE username = $1", form_data.username)

    if not row or not await run_in_threadpool(verify_password, form_data.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": str(row["id"])})
    return {"access_token": access_token, "token_type": "bearer"}


def _decode_token(token: str) -> int:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    return _decode_token(token)


async def get_optional_user_id(token: str | None = Depends(oauth2_scheme_optional)) -> int | None:
    return _decode_token(token) if token else None
