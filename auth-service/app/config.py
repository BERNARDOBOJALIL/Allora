from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongo_uri: str = "mongodb://mongodb:27017"
    mongo_db_name: str = "allora_auth"

    jwt_secret: str = "change_this_secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    refresh_token_expire_days: int = 30
    verification_code_expire_minutes: int = 10
    dev_return_codes: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
