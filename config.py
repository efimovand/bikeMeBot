import json
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent
INVITED_USERS_FILE = BASE_DIR / "invited_users.json"


def load_invited_users() -> set[int]:
    if not INVITED_USERS_FILE.exists():
        return set()
    try:
        data = json.loads(INVITED_USERS_FILE.read_text(encoding="utf-8"))
        return {int(uid) for uid in data}
    except Exception:
        return set()


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