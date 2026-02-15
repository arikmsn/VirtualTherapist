"""Application configuration using Pydantic Settings"""

from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "TherapyCompanion.AI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str
    ENCRYPTION_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Database
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI Configuration
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    AI_PROVIDER: Literal["openai", "anthropic"] = "anthropic"
    AI_MODEL: str = "claude-3-5-sonnet-20241022"
    TEMPERATURE: float = 0.7
    MAX_TOKENS: int = 2000

    # Audio Processing
    MAX_AUDIO_SIZE_MB: int = 25
    SUPPORTED_AUDIO_FORMATS: str = "mp3,wav,m4a,ogg"

    # Privacy & Security (CRITICAL)
    DATA_REGION: Literal["IL", "EU"] = "IL"
    ENABLE_ENCRYPTION: bool = True
    ENABLE_AUDIT_LOG: bool = True
    GDPR_COMPLIANT: bool = True

    # Message Approval
    REQUIRE_THERAPIST_APPROVAL: bool = True
    AUTO_APPROVE_TIMEOUT_HOURS: int = 24

    # Session Settings
    SESSION_SUMMARY_AUTO_SAVE: bool = True
    SESSION_SUMMARY_BACKUP: bool = True

    # Language
    DEFAULT_LANGUAGE: Literal["he", "en"] = "he"
    RTL_SUPPORT: bool = True

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/therapy_companion.log"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )


# Global settings instance
settings = Settings()
