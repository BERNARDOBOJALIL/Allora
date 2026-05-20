from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongodb_url: str = "mongodb://root:password@mongodb:27017"
    mongodb_db: str = "match_service"
    auth_service_url: str = "http://auth-service:8000"
    location_service_url: str = "http://location-service:8003"
    profile_agent_url: str = "https://alloraagent.onrender.com"
    log_level: str = "INFO"
    
    # Matching algorithm parameters
    max_distance_km: float = 50.0  # Radio de búsqueda máximo
    min_compatibility_score: float = 0.5  # Score mínimo de compatibilidad
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
