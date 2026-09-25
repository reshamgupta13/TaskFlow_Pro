import logging
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    PROJECT_NAME: str = "TaskFlow Pro"
    API_V1_STR: str = "/api"
    DATABASE_URL: str = "sqlite:///./taskflow.db"
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]

    # Optional LLM API keys
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    # Authentication
    # No hardcoded default: if SECRET_KEY isn't set via env/.env, a random
    # one is generated at startup below. That key is process-local and
    # changes on every restart, so existing JWTs won't survive a restart
    # unless a persistent SECRET_KEY is provided via environment/.env.
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

if not settings.SECRET_KEY:
    settings.SECRET_KEY = secrets.token_urlsafe(32)
    logger.warning(
        "SECRET_KEY not set via environment/.env — generated a random, "
        "process-local key for this run. Existing login tokens will be "
        "invalidated on restart. Set SECRET_KEY in your environment for "
        "a persistent/production deployment."
    )

