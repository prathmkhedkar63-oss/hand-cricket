import hashlib
import hmac
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

    # Webhook vs Polling ('auto' uses RENDER_EXTERNAL_URL/WEBHOOK_URL when set, or 'true'/'false')
    USE_WEBHOOK: str = os.environ.get("USE_WEBHOOK", "auto")
    WEBHOOK_URL: Optional[str] = os.environ.get("WEBHOOK_URL")
    WEBHOOK_PATH: str = os.environ.get("WEBHOOK_PATH", "/telegram/webhook")
    WEBHOOK_SECRET: Optional[str] = os.environ.get("WEBHOOK_SECRET")

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

    def resolve_webhook_url(self) -> Optional[str]:
        """Returns full public HTTPS webhook URL when webhook mode is active, else None."""
        mode = (self.USE_WEBHOOK or "auto").strip().lower()
        if mode in {"0", "false", "no", "polling"}:
            return None
        path = self.WEBHOOK_PATH if self.WEBHOOK_PATH.startswith("/") else f"/{self.WEBHOOK_PATH}"
        explicit = (self.WEBHOOK_URL or "").strip()
        if explicit:
            if explicit.endswith(path):
                return explicit
            return f"{explicit.rstrip('/')}{path}"
        render_url = (os.environ.get("RENDER_EXTERNAL_URL") or "").strip()
        if render_url and mode in {"auto", "1", "true", "yes", "webhook"}:
            return f"{render_url.rstrip('/')}{path}"
        return None

    def resolve_webhook_secret(self) -> str:
        """Stable deterministic Telegram secret_token so zero-downtime Render containers match."""
        if self.WEBHOOK_SECRET and self.WEBHOOK_SECRET.strip():
            return self.WEBHOOK_SECRET.strip()
        digest = hmac.new(
            self.SECRET_KEY.encode("utf-8"),
            self.BOT_TOKEN.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return digest[:48]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

settings = Settings()

# Ensure critical data and backup directories exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
