from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
    )

    # Database
    database_url: str
    database_url_sync: str

    # TG token
    bot_token: str

    # Media
    media_dir: Path = Path("media")

    # Proxy
    proxy_tg_url: str  # TG
    proxy_ai_url: str  # AI


settings = Settings()
