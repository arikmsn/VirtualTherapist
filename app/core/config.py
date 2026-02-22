"""Application configuration using Pydantic Settings"""

from typing import Literal
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_PATTERNS = [
    "your-openai-key", "your-anthropic-key",
    "sk-your-", "replace_with_your", "your-",
    "change-me", "placeholder",
]


def is_placeholder_key(value: str | None) -> bool:
    """Check if an API key is missing or a placeholder."""
    if not value or not value.strip():
        return True
    lower = value.strip().lower()
    return any(p in lower for p in _PLACEHOLDER_PATTERNS)


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "TherapyCompanion.AI"
    APP_VERSION: str = "1.0.0"
    CLINIC_NAME: str = "TherapyCompanion"  # Shown in appointment reminder templates
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

    # WhatsApp / Twilio (Messages Center v1 — Phase C)
    TWILIO_ACCOUNT_SID: str | None = None
    # API Key auth (preferred over Auth Token):
    TWILIO_API_KEY_SID: str | None = None     # starts with SK...
    TWILIO_API_KEY_SECRET: str | None = None
    # Legacy Auth Token (still accepted if API Key not set):
    TWILIO_AUTH_TOKEN: str | None = None
    TWILIO_WHATSAPP_NUMBER: str | None = None  # e.g. "whatsapp:+14155238886"

    # CORS
    # Comma-separated list of allowed frontend origins.
    # In production set to your Vercel URL, e.g. "https://app.vercel.app".
    # Defaults to "*" so local development works without extra config.
    CORS_ORIGINS: str = "*"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/therapy_companion.log"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

    @model_validator(mode="after")
    def validate_ai_keys(self) -> "Settings":
        key_field = (
            "ANTHROPIC_API_KEY" if self.AI_PROVIDER == "anthropic"
            else "OPENAI_API_KEY"
        )
        key_value = getattr(self, key_field)

        if is_placeholder_key(key_value):
            msg = (
                f"{key_field} is missing or a placeholder. "
                f"AI features (chat, summaries) will not work. "
                f"Set a valid key in .env for AI_PROVIDER='{self.AI_PROVIDER}'."
            )
            if self.ENVIRONMENT == "production":
                raise ValueError(msg)
            else:
                from loguru import logger
                logger.warning(msg)

        return self


# Global settings instance
settings = Settings()
