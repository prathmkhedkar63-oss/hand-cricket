import os
from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Telegram Bot
    BOT_TOKEN: str = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz_EXAMPLE"
    BOT_USERNAME: str = "HandCricketOfficialBot"
    SUPER_ADMIN_ID: int = 123456789
    SUPER_ADMIN_USERNAME: str = "prathamesh63"
    # Default Telegram Group ID (Optional - tournaments automatically bind to whichever group they are run in)
    DEFAULT_GROUP_ID: Optional[int] = None

    # Backend API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = int(os.environ.get("PORT", os.environ.get("API_PORT", 8000)))
    SECRET_KEY: str = "super-secret-jwt-key-change-this-in-production-1234567890"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "adminpassword123"

    # External Database (Optional PostgreSQL / Supabase / Neon URL; falls back to local JSON if unset)
    DATABASE_URL: Optional[str] = os.environ.get("DATABASE_URL")

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"
    BACKUP_DIR: Path = Path(__file__).resolve().parent.parent / "data" / "backups"
    
    # Backups & Integrity
    BACKUP_INTERVAL_MINUTES: int = 60
    MAX_BACKUP_COPIES: int = 10

    # Game Rules Defaults
    DEFAULT_INNINGS_LIMIT: int = 2
    DEFAULT_WICKETS_LIMIT: int = 1
    DEFAULT_MAX_BALLS: int = 36  # 6 overs per innings default, 0 for unlimited until out
    SOLO_TOURNAMENT_COUNTDOWN_SECONDS: int = 120

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

settings = Settings()

# Ensure critical data and backup directories exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
