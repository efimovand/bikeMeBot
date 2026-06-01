import json
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent
INVITED_USERS_FILE = BASE_DIR / "invited_users.json"


# Кеш invited_users инвалидируется при изменении mtime файла —
# редактирование файла на диске подхватится автоматически без рестарта бота.
_invited_users_cache: tuple[frozenset[int], float] | None = None


def load_invited_users() -> set[int]:
    global _invited_users_cache

    if not INVITED_USERS_FILE.exists():
        _invited_users_cache = None
        return set()

    mtime = INVITED_USERS_FILE.stat().st_mtime
    if _invited_users_cache is not None and _invited_users_cache[1] == mtime:
        return set(_invited_users_cache[0])

    try:
        data = json.loads(INVITED_USERS_FILE.read_text(encoding="utf-8"))
        users = frozenset(int(uid) for uid in data)
        _invited_users_cache = (users, mtime)
        return set(users)
    except Exception:
        return set()


# ---------------------------------------------------------------------------
# Admin users (mirror of invited_users: JSON list of tg_id, mtime-cached).
# ---------------------------------------------------------------------------
ADMIN_USERS_FILE = BASE_DIR / "admin_users.json"

_admin_users_cache: tuple[frozenset[int], float] | None = None


def load_admin_users() -> set[int]:
    global _admin_users_cache

    if not ADMIN_USERS_FILE.exists():
        _admin_users_cache = None
        return set()

    mtime = ADMIN_USERS_FILE.stat().st_mtime
    if _admin_users_cache is not None and _admin_users_cache[1] == mtime:
        return set(_admin_users_cache[0])

    try:
        data = json.loads(ADMIN_USERS_FILE.read_text(encoding="utf-8"))
        users = frozenset(int(uid) for uid in data)
        _admin_users_cache = (users, mtime)
        return set(users)
    except Exception:
        return set()


def is_admin(tg_id: int) -> bool:
    return tg_id in load_admin_users()


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