from pathlib import Path
from config import settings
from models import User
from database import photoset_is_complete


BASE_DIR = Path(settings.media_dir)

_config_msg_ids: dict[int, int] = {}


def get_media_path(relative_path: str) -> Path:
    return BASE_DIR / relative_path


def read_media_bytes(relative_path: str) -> bytes:
    return get_media_path(relative_path).read_bytes()


def config_text(user: User) -> str:
    if user.bike_file:
        bike_line = f"🏍 <b>Мотоцикл:</b> {user.bike_file.bike.brand} {user.bike_file.bike.model} / {user.bike_file.color.name}"
    else:
        bike_line = "🏍 <b>Мотоцикл:</b> <i>не выбран</i>"

    if user.location:
        location_label = user.location.description or user.location.name
        location_line = f"📍 <b>Локация:</b> {location_label}"
    else:
        location_line = "📍 <b>Локация:</b> <i>по умолчанию</i>"

    if user.helmet_file:
        helmet_line = f"🪖 <b>Шлем:</b> {user.helmet_file.helmet.brand} {user.helmet_file.helmet.model} / {user.helmet_file.color.name}"
    else:
        helmet_line = "🪖 <b>Шлем:</b> <i>не выбран</i>"

    if user.jacket_file:
        jacket_line = f"🧥 <b>Куртка:</b> {user.jacket_file.jacket.brand} {user.jacket_file.jacket.model} / {user.jacket_file.color.name}"
    else:
        jacket_line = "🧥 <b>Куртка:</b> <i>не выбрана</i>"

    if user.suit_file:
        suit_line = f"🏁 <b>Комбинезон:</b> {user.suit_file.suit.brand} {user.suit_file.suit.model} / {user.suit_file.color.name}"
    else:
        suit_line = "🏁 <b>Комбинезон:</b> <i>не выбран</i>"

    if user.glove_file:
        glove_line = f"🧤 <b>Перчатки:</b> {user.glove_file.glove.brand} {user.glove_file.glove.model} / {user.glove_file.color.name}"
    else:
        glove_line = "🧤 <b>Перчатки:</b> <i>не выбраны</i>"

    if user.boot_file:
        boot_line = f"🥾 <b>Ботинки:</b> {user.boot_file.boot.brand} {user.boot_file.boot.model} / {user.boot_file.color.name}"
    else:
        boot_line = "🥾 <b>Ботинки:</b> <i>не выбраны</i>"

    balance_line = f"⭐️ <b>Баланс:</b> {user.balance}" if user.balance > 0 else ""

    photos_line = (
        "📷 <b>Ваши фото:</b> ☑️"
        if photoset_is_complete(user.photoset)
        else "📷 <b>Ваши фото:</b> <i>не загружены</i>"
    )

    return (
        "⚙️ <b>Текущая конфигурация:</b>\n\n"
        f"{bike_line}\n"
        f"{location_line}\n\n"
        f"{helmet_line}\n"
        f"{jacket_line}\n"
        f"{suit_line}\n"
        f"{glove_line}\n"
        f"{boot_line}\n\n"
        f"{balance_line}\n"
        f"{photos_line}"
    )