from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Ledgerline Document Intake API"
    database_url: str = "sqlite:///./document_intake.db"
    review_threshold: float = 0.85
    upload_dir: Path = Path("data/uploads")
    max_upload_bytes: int = 10 * 1024 * 1024
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    google_sheets_credentials_file: Path | None = None
    google_sheets_spreadsheet_id: str | None = None
    google_sheets_range: str = "Approved Records!A:I"
    gmail_client_file: Path = Path("credentials/gmail-client.json")
    gmail_token_file: Path = Path("credentials/gmail-token.json")
    gmail_query: str = "has:attachment filename:pdf newer_than:30d"
    gmail_summary_recipient: str | None = None
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
