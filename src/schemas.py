from datetime import datetime, timedelta, timezone

from pydantic import AnyHttpUrl, BaseModel, Field, computed_field

from src.config import settings


class UserCreate(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class LinkCreate(BaseModel):
    original_url: AnyHttpUrl
    custom_alias: str | None = None
    expires_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30), examples=[datetime.now(timezone.utc) + timedelta(days=30)]
    )


class LinkUpdate(BaseModel):
    original_url: AnyHttpUrl


def get_short_url(short_code: str) -> str:
    return f"{settings.base_url.rstrip('/')}/{short_code}"


class LinkResponse(BaseModel):
    short_code: str
    original_url: str
    expires_at: datetime | None = None

    @computed_field
    @property
    def short_url(self) -> str:
        return get_short_url(self.short_code)


class LinkStats(BaseModel):
    original_url: str
    created_at: datetime
    last_used_at: datetime | None
    clicks: int


class LinkListItem(BaseModel):
    short_code: str
    original_url: str
    clicks: int
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None

    @computed_field
    @property
    def short_url(self) -> str:
        return get_short_url(self.short_code)


class LinksListResponse(BaseModel):
    links: list[LinkListItem]
    total: int
    page: int
    per_page: int
