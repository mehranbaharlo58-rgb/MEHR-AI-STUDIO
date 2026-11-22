"""Environment-based configuration."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = "MEHR AI STUDIO"
    database_path: Path = Path(os.getenv("MEHR_DB_PATH", "mehr_ai_studio.sqlite3"))
    provider_base_url: str = os.getenv("AI_BASE_URL", "").rstrip("/")
    provider_api_key: str = os.getenv("AI_API_KEY", "")
    provider_model: str = os.getenv("AI_MODEL", "")
    request_timeout: float = float(os.getenv("AI_TIMEOUT_SECONDS", "45"))
    provider_max_attempts: int = min(5, max(1, int(os.getenv("AI_MAX_ATTEMPTS", "3"))))
    provider_retry_backoff: float = min(10.0, max(0.0, float(os.getenv("AI_RETRY_BACKOFF_SECONDS", "0.5"))))


settings = Settings()
