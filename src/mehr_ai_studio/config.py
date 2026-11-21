"""Environment-based configuration."""
from dataclasses import dataclass
import os
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

settings = Settings()
