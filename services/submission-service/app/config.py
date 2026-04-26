from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+asyncpg://worknomads:changeme@postgres:5432/worknomads"
    )
    rabbitmq_url: str = "amqp://worknomads:changeme@rabbitmq:5672/"
    minio_endpoint: str = "minio:9000"
    minio_public_endpoint: str | None = None
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "worknomads-photos"
    minio_secure: bool = False
    minio_bucket_public: bool = False

    jwt_secret_key: str = "super-secret-jwt-key-change-in-production"
    jwt_algorithm: str = "HS256"

    classification_queue: str = "classification_tasks"
    max_photo_size_bytes: int = 10 * 1024 * 1024  # 10 MB

    app_env: str = "development"
    log_level: str = "INFO"


settings = Settings()
