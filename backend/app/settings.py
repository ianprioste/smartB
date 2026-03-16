"""Application settings and configuration."""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application configuration."""
    
    # Core
    DEBUG: bool = False
    PROJECT_NAME: str = "smartBling v2"
    VERSION: str = "0.1.0"
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/smartbling"
    )
    
    # Redis
    REDIS_URL: str = os.getenv(
        "REDIS_URL",
        "redis://localhost:6379/0"
    )
    
    # Bling OAuth2
    BLING_CLIENT_ID: str = os.getenv("BLING_CLIENT_ID", "")
    BLING_CLIENT_SECRET: str = os.getenv("BLING_CLIENT_SECRET", "")
    BLING_REDIRECT_URI: str = os.getenv(
        "BLING_REDIRECT_URI",
        ""
    )
    BLING_AUTH_URL: str = "https://www.bling.com.br/Api/v3/oauth/authorize"
    BLING_TOKEN_URL: str = "https://www.bling.com.br/Api/v3/oauth/token"
    BLING_API_BASE_URL: str = "https://www.bling.com.br/Api/v3"
    
    # JWT (internal)
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "dev-secret-key-change-in-production"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Celery
    CELERY_BROKER_URL: str = os.getenv(
        "CELERY_BROKER_URL",
        "redis://localhost:6379/1"
    )
    CELERY_RESULT_BACKEND: str = os.getenv(
        "CELERY_RESULT_BACKEND",
        "redis://localhost:6379/2"
    )
    
    # CORS
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:80")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
