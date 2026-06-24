from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration. Field names map to UPPER_CASE env vars."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://lablumen:lablumen@localhost:5432/lablumen"
    redis_url: str = "redis://localhost:6379/0"

    aws_region: str = "us-east-1"
    cognito_user_pool_id: str = ""
    cognito_app_client_id: str = ""

    notifications_queue_url: str = ""
    slot_lock_ttl_seconds: int = 300

    # Pass as a JSON array: CORS_ORIGINS='["*"]' or CORS_ORIGINS='["http://localhost:5173"]'
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
