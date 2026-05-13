from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    service_name: str = "location-service"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8003
    debug: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
