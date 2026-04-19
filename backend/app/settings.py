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
    GIT_COMMIT: str = os.getenv("GIT_COMMIT", "unknown")
    BUILD_ID: str = os.getenv("BUILD_ID", "unknown")
    BUILD_TIMESTAMP: str = os.getenv("BUILD_TIMESTAMP", "unknown")
    
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
    ORDERS_INCREMENTAL_SYNC_MINUTES: int = int(os.getenv("ORDERS_INCREMENTAL_SYNC_MINUTES", "15"))
    ORDERS_EMAIL_ENRICHMENT_MINUTES: int = int(os.getenv("ORDERS_EMAIL_ENRICHMENT_MINUTES", "0"))
    ORDERS_EMAIL_ENRICHMENT_BATCH_SIZE: int = int(os.getenv("ORDERS_EMAIL_ENRICHMENT_BATCH_SIZE", "20"))
    ORDERS_EMAIL_ENRICHMENT_MAX_CONTACTS: int = int(os.getenv("ORDERS_EMAIL_ENRICHMENT_MAX_CONTACTS", "20"))
    MASTER_ADMIN_EMAIL: str = os.getenv("MASTER_ADMIN_EMAIL", "ian.prioste@useruach.com.br").strip().lower()

    # Bling Webhooks
    BLING_WEBHOOK_SECRET: str = os.getenv("BLING_WEBHOOK_SECRET", "")
    WEBHOOKS_ENABLED: bool = os.getenv("WEBHOOKS_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
    WEBHOOK_MAX_RETRIES: int = int(os.getenv("WEBHOOK_MAX_RETRIES", "5"))
    WEBHOOK_RETRY_BASE_DELAY_S: int = int(os.getenv("WEBHOOK_RETRY_BASE_DELAY_S", "10"))
    PRODUCT_SYNC_MODE: str = os.getenv("PRODUCT_SYNC_MODE", "webhook_first").strip().lower()
    PRODUCT_SYNC_DIRECT_FALLBACK: bool = os.getenv("PRODUCT_SYNC_DIRECT_FALLBACK", "false").strip().lower() in {"1", "true", "yes", "on"}
    PASSWORD_RESET_CODE_EXPIRE_MINUTES: int = int(os.getenv("PASSWORD_RESET_CODE_EXPIRE_MINUTES", "5"))
    PASSWORD_RESET_CODE_LENGTH: int = int(os.getenv("PASSWORD_RESET_CODE_LENGTH", "6"))
    
    # CORS
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:80")

    # SMTP / password reset
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", PROJECT_NAME)
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").strip().lower() in {"1", "true", "yes", "on"}
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "false").strip().lower() in {"1", "true", "yes", "on"}

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG")
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"


settings = Settings()
