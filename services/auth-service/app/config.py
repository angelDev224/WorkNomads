from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = (
        "postgresql+asyncpg://worknomads:changeme@postgres:5432/worknomads"
    )

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # JWT
    jwt_secret_key: str = "super-secret-jwt-key-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # Bootstrap admin (optional, startup-only provisioning)
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None


settings = Settings()
