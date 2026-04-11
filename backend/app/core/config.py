from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Configurações da aplicação"""
    
    # API Bling (OAuth2 v3)
    BLING_CLIENT_ID: str = ""
    BLING_CLIENT_SECRET: str = ""
    BLING_REDIRECT_URI: str = "http://localhost:8000/callback"
    BLING_API_KEY: str = ""  # opcional se usar v2
    BLING_API_BASE_URL: str = "https://api.bling.com.br/Api/v3"

    # Tokens OAuth2 (salvos no .env ao configurar)
    BLING_ACCESS_TOKEN: str = ""
    BLING_REFRESH_TOKEN: str = ""
    BLING_TOKEN_TYPE: str = "Bearer"
    BLING_EXPIRES_IN: int | None = None

    # Server
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    DEBUG: bool = True
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # Upload/Export
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB
    UPLOAD_FOLDER: str = "uploads"
    EXPORT_FOLDER: str = "exports"

    # Ngrok
    NGROK_ENABLE: bool = False
    NGROK_BIN: str = "ngrok"
    NGROK_AUTHTOKEN: str = ""
    NGROK_REGION: str = ""  # ex.: sa, us, eu
    NGROK_UPDATE_REDIRECT: bool = True  # atualizar BLING_REDIRECT_URI no .env com a URL pública

    # Config Pydantic Settings (aceita extras e carrega .env)
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow",
    )


settings = Settings()
