from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    service_name: str = "location-service"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8003
    debug: bool = False
    auth_jwt_secret: str = "change_this_secret"
    auth_jwt_algorithm: str = "HS256"
    auth_service_url: str = "http://auth-service:8000"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
