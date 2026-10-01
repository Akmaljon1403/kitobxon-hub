"""Application configuration.

All configuration comes from environment variables (or a local ``.env`` file).
Nothing secret is hard-coded: the defaults below are only safe for local development
and the application refuses to start in production with insecure values.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_DEV_SECRET = "dev-only-insecure-secret-key-change-me-0123456789"  # noqa: S105

# libpq-style query parameters that asyncpg does not understand.
_LIBPQ_ONLY_PARAMS = {"sslmode", "channel_binding", "gssencmode", "target_session_attrs"}


def normalize_database_url(raw_url: str) -> tuple[str, dict[str, Any]]:
    """Convert a provider-style PostgreSQL URL into an SQLAlchemy asyncpg URL.

    Hosting providers (Neon, Render, Supabase, ...) hand out URLs such as
    ``postgres://user:pw@host/db?sslmode=require&channel_binding=require``.
    asyncpg needs the ``postgresql+asyncpg`` scheme and receives SSL settings as a
    connect argument, so this function rewrites the URL and returns
    ``(url, connect_args)``.
    """
    parts = urlsplit(raw_url.strip())
    scheme = parts.scheme
    if scheme in {"postgres", "postgresql", "postgresql+asyncpg", "postgresql+psycopg", "postgresql+psycopg2"}:
        scheme = "postgresql+asyncpg"
    else:
        raise ValueError("DATABASE_URL must be a PostgreSQL URL (postgresql://...)")

    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    connect_args: dict[str, Any] = {}
    sslmode = query.pop("sslmode", None) or query.pop("ssl", None)
    for param in _LIBPQ_ONLY_PARAMS:
        query.pop(param, None)
    if sslmode and sslmode != "disable":
        # asyncpg accepts libpq sslmode names (require, verify-ca, verify-full, prefer, allow).
        connect_args["ssl"] = sslmode

    url = urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    return url, connect_args


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- General ----
    environment: Literal["development", "test", "production"] = "development"
    app_name: str = "Kitobxon Hub"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    log_json: bool = True
    api_docs_enabled: bool = True
    timezone: str = "Asia/Tashkent"
    # Render sets RENDER_EXTERNAL_URL automatically, so the variable is optional there.
    public_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PUBLIC_BASE_URL", "RENDER_EXTERNAL_URL"),
        description="Public HTTPS address of the backend, e.g. https://kitobxon.example.uz",
    )
    static_dir: str = Field(default="static", description="Directory with the built Mini App and Admin Panel")
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # ---- Database / cache ----
    database_url: str = "postgresql://postgres:postgres@localhost:5432/kitobxon"
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=5, ge=0, le=50)
    db_echo: bool = False
    redis_url: str | None = None

    # ---- Security ----
    secret_key: SecretStr = SecretStr(_DEV_SECRET)
    access_token_ttl_minutes: int = Field(default=60 * 24, ge=5)
    admin_token_ttl_minutes: int = Field(default=60 * 12, ge=5)
    admin_login_link_ttl_seconds: int = Field(default=300, ge=60, le=3600)
    super_admin_telegram_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)

    # ---- Telegram ----
    bot_token: SecretStr | None = None
    bot_username: str | None = None
    # webhook: Telegram calls PUBLIC_BASE_URL/telegram/webhook (production);
    # polling: run `python -m app.bot.polling` separately (local development); disabled: no bot.
    bot_mode: Literal["webhook", "polling", "disabled"] = "webhook"
    telegram_webapp_url: str | None = None
    telegram_webhook_secret: SecretStr | None = None
    init_data_max_age_seconds: int = Field(default=60 * 60 * 24, ge=60)

    # ---- File storage ----
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_path: str = "./storage"
    storage_endpoint: str | None = None
    storage_region: str = "auto"
    storage_access_key: SecretStr | None = None
    storage_secret_key: SecretStr | None = None
    storage_bucket: str | None = None

    # ---- AI report drafting (optional) ----
    ai_api_key: SecretStr | None = None
    ai_model: str = "claude-sonnet-5-5"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]
        return value

    @field_validator("super_admin_telegram_ids", mode="before")
    @classmethod
    def _split_ids(cls, value: Any) -> Any:
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        return value

    @field_validator(
        "public_base_url",
        "telegram_webapp_url",
        "bot_token",
        "bot_username",
        "telegram_webhook_secret",
        "redis_url",
        "storage_endpoint",
        "storage_access_key",
        "storage_secret_key",
        "storage_bucket",
        "ai_api_key",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, value: Any) -> Any:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("bot_username")
    @classmethod
    def _strip_at(cls, value: str | None) -> str | None:
        return value.lstrip("@") if value else value

    @model_validator(mode="after")
    def _check_production_safety(self) -> Settings:
        normalize_database_url(self.database_url)  # raises early on a malformed URL
        if self.environment == "production":
            secret = self.secret_key.get_secret_value()
            if secret == _DEV_SECRET or len(secret) < 32:
                raise ValueError("SECRET_KEY must be set to a random value of at least 32 characters in production")
            if self.storage_backend == "s3" and not (
                self.storage_endpoint and self.storage_bucket and self.storage_access_key and self.storage_secret_key
            ):
                raise ValueError("STORAGE_* variables are required when STORAGE_BACKEND=s3")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def base_url(self) -> str | None:
        return self.public_base_url.rstrip("/") if self.public_base_url else None

    @property
    def webapp_url(self) -> str | None:
        """Mini App address; defaults to the copy served by this backend under /app/."""
        if self.telegram_webapp_url:
            return self.telegram_webapp_url
        return f"{self.base_url}/app/" if self.base_url else None

    @property
    def bot_enabled(self) -> bool:
        return self.bot_token is not None and self.bot_mode != "disabled"

    @property
    def sqlalchemy_database(self) -> tuple[str, dict[str, Any]]:
        return normalize_database_url(self.database_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
