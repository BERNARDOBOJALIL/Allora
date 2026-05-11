from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379/0"
    auth_service_url: str = "http://auth-service:8000"
    jwt_algorithm: str = "RS256"
    jwt_issuer: str = "auth-service"

    users_service_url: str | None = None
    chat_service_url: str | None = None
    matches_service_url: str | None = None
    notifications_service_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
