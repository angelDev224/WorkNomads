from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://worknomads:changeme@postgres:5432/worknomads"
    rabbitmq_url: str = "amqp://worknomads:changeme@rabbitmq:5672/"
    classification_queue: str = "classification_tasks"
    classifier_version: str = "v1.0.0"
    log_level: str = "INFO"


settings = Settings()
