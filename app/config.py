from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Document Intake and Review API"
    database_url: str = "sqlite:///./document_intake.db"
    review_threshold: float = 0.85
    upload_dir: Path = Path("data/uploads")
    max_upload_bytes: int = 10 * 1024 * 1024
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

