from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "SentiNews AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")  # development|production
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecretkey")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # DB
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinews")
    
    # Qdrant
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    
    # LLM & External APIs
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")
    FINNHUB_API_KEY: str = os.getenv("FINNHUB_API_KEY", "")
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
