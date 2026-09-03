from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base backend directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Finance Controller"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./finance.db"

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
    DATA_DIR: Path = BASE_DIR / "data"
    RAW_DATA_DIR: Path = BASE_DIR / "data" / "raw"
    PROCESSED_DATA_DIR: Path = BASE_DIR / "data" / "processed"
    GROUND_TRUTH_DIR: Path = BASE_DIR / "data" / "ground_truth"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

# Ensure data directories exist
settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.GROUND_TRUTH_DIR.mkdir(parents=True, exist_ok=True)
