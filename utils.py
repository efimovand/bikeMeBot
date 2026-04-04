from pathlib import Path
from config import settings
from models import User
from database import photoset_is_complete


BASE_DIR = Path(settings.media_dir)


def get_media_path(relative_path: str) -> Path:
    return BASE_DIR / relative_path


def read_media_bytes(relative_path: str) -> bytes:
    return get_media_path(relative_path).read_bytes()


def config_text(user: User) -> str:
    if user.bike_file:
        bike_line = f"🏍 Мотоцикл: <b>{user.bike_file.bike.brand} {user.bike_file.bike.model} / {user.bike_file.color.name}</b>"
    else:
        bike_line = "🏍 Мотоцикл: <b>не выбран</b>"

    if user.helmet_file:
        helmet_line = f"🪖 Шлем: <b>{user.helmet_file.helmet.brand} {user.helmet_file.helmet.model} / {user.helmet_file.color.name}</b>"
    else:
        helmet_line = "🪖 Шлем: <b>не выбран</b>"

    if user.jacket_file:
        jacket_line = f"🧥 Куртка: <b>{user.jacket_file.jacket.brand} {user.jacket_file.jacket.model} / {user.jacket_file.color.name}</b>"
    else:
        jacket_line = "🧥 Куртка: <b>не выбрана</b>"

    if user.glove_file:
        glove_line = f"🧤 Перчатки: <b>{user.glove_file.glove.brand} {user.glove_file.glove.model} / {user.glove_file.color.name}</b>"
    else:
        glove_line = "🧤 Перчатки: <b>не выбраны</b>"

    photos_line = (
        "📷 Ваши фото: ✅"
        if photoset_is_complete(user.photoset)
        else "📷 Ваши фото: <b>не загружены</b>"
    )

    return (
        "⚙️ <b>Текущая конфигурация:</b>\n\n"
        f"{bike_line}\n"
        f"{helmet_line}\n"
        f"{jacket_line}\n"
        f"{glove_line}\n"
        f"{photos_line}"
    )
