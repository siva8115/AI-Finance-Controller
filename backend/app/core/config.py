import os
import tempfile
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base backend directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

IS_VERCEL = bool(os.environ.get("VERCEL")) or bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

def get_default_db_url() -> str:
    env_db = os.environ.get("DATABASE_URL")
    if env_db:
        return env_db
    if IS_VERCEL:
        tmp_db = Path(tempfile.gettempdir()) / "finance.db"
        return f"sqlite:///{tmp_db}"
    return "sqlite:///./finance.db"

def get_data_dir(subdir: str) -> Path:
    if IS_VERCEL:
        return Path(tempfile.gettempdir()) / "data" / subdir
    return BASE_DIR / "data" / subdir


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Finance Controller"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = get_default_db_url()

    # AI Config
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"

    # Evidence Escalation & Budget Limits
    MAX_EVIDENCE_RECORDS: int = 25
    MAX_RELATED_RECORDS: int = 10
    MAX_EXTENDED_RECORDS: int = 20
    MAX_PROMPT_LENGTH: int = 8000
    MAX_INVESTIGATION_ATTEMPTS: int = 3
    CONCURRENT_INVESTIGATION_LIMIT: int = 5

    # Confidence Thresholds
    CONFIDENCE_HIGH_THRESHOLD: float = 0.90
    CONFIDENCE_MEDIUM_THRESHOLD: float = 0.60

    # Reconciliation Engine Defaults
    SETTLEMENT_WINDOW_DAYS: int = 3
    MONETARY_TOLERANCE: float = 0.01

    # Paths
    DATA_DIR: Path = Path(tempfile.gettempdir()) / "data" if IS_VERCEL else BASE_DIR / "data"
    RAW_DATA_DIR: Path = get_data_dir("raw")
    PROCESSED_DATA_DIR: Path = get_data_dir("processed")
    GROUND_TRUTH_DIR: Path = get_data_dir("ground_truth")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

# Ensure data directories exist safely
for d in [settings.RAW_DATA_DIR, settings.PROCESSED_DATA_DIR, settings.GROUND_TRUTH_DIR]:
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

