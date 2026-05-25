import asyncio
import database as db
from models import User


_NO_HELMET = "IMPORTANT: The person must be shown without any helmet, with their head completely bare."
_NO_JACKET = "IMPORTANT: The person must be shown in their own clothing — no motorcycle jacket or suit."
_NO_GLOVE = "IMPORTANT: The person must be shown without motorcycle gloves, bare hands."
_NO_BOOT = "IMPORTANT: The person must be shown without motorcycle boots, in their own footwear."


def _format_dict_prompt(prompts: list, key: str, raw: str | None) -> str:
    """Безопасно применить шаблон из dictionary_prompt. Если нет — пустая строка."""
    if not prompts:
        return ""
    return prompts[0].text.format(**{key: raw or ""})


async def make_final_prompt(user: User) -> str:
    """Собрать финальный промпт для генерации.

    user должен быть загружен через `get_user_by_tg_id` — со всеми selectinload-ами
    из `_USER_OPTIONS`, чтобы доступ к user.bike_file.bike.prompt и т.д. не лазал в БД.
    """
    # --- Параллельно подтягиваем нужные шаблоны из dictionary_prompt ---
    needed_types: list[str] = ["default"]
    if user.helmet_file is not None:
        needed_types.append("helmet")
    if user.jacket_file is not None:
        needed_types.append("jacket")
    if user.suit_file is not None:
        needed_types.append("suit")
    if user.glove_file is not None:
        needed_types.append("glove")
    if user.boot_file is not None:
        needed_types.append("boot")

    fetched = await asyncio.gather(*[db.get_prompts_by_type(t) for t in needed_types])
    dict_prompts: dict[str, list] = dict(zip(needed_types, fetched))

    # --- Байк + локация (всё уже эагерно загружено в user) ---
    raw_bike_prompt = user.bike_file.bike.prompt
    if user.location is not None:
        location_prompt = user.location.prompt
    else:
        location_prompt = user.bike_file.bike.location.prompt
    bike_prompt = f"Motorcycle ergonomics and scale: {raw_bike_prompt}" if raw_bike_prompt else ""

    # --- Шлем ---
    if user.helmet_file is not None:
        helmet_prompt = _format_dict_prompt(
            dict_prompts.get("helmet", []),
            "helmet_prompt",
            user.helmet_file.helmet.prompt,
        )
    else:
        helmet_prompt = _NO_HELMET

    # --- Куртка / Комбинезон (взаимоисключающие) ---
    if user.jacket_file is not None:
        jacket_prompt = _format_dict_prompt(
            dict_prompts.get("jacket", []),
            "jacket_prompt",
            user.jacket_file.jacket.prompt,
        )
        suit_prompt = ""
    elif user.suit_file is not None:
        suit_prompt = _format_dict_prompt(
            dict_prompts.get("suit", []),
            "suit_prompt",
            user.suit_file.suit.prompt,
        )
        jacket_prompt = ""
    else:
        jacket_prompt = _NO_JACKET
        suit_prompt = ""

    # --- Перчатки ---
    if user.glove_file is not None:
        glove_prompt = _format_dict_prompt(
            dict_prompts.get("glove", []),
            "glove_prompt",
            user.glove_file.glove.prompt,
        )
    else:
        glove_prompt = _NO_GLOVE

    # --- Ботинки ---
    if user.boot_file is not None:
        boot_prompt = _format_dict_prompt(
            dict_prompts.get("boot", []),
            "boot_prompt",
            user.boot_file.boot.prompt,
        )
    else:
        boot_prompt = _NO_BOOT

    # --- Финальный промпт ---
    default_prompts = dict_prompts.get("default", [])
    if not default_prompts:
        raise RuntimeError("No 'default' prompt in dictionary_prompt — cannot build final prompt")

    return default_prompts[0].text.format(
        helmet_photo_mention=", a photo of a motorcycle helmet" if user.helmet_file is not None else "",
        jacket_photo_mention=", a photo of a motorcycle jacket" if user.jacket_file is not None else "",
        suit_photo_mention=", a photo of a motorcycle suit" if user.suit_file is not None else "",
        glove_photo_mention=", a photo of motorcycle gloves" if user.glove_file is not None else "",
        boot_photo_mention=", a photo of motorcycle boots" if user.boot_file is not None else "",
        bike_prompt=bike_prompt,
        location_prompt=location_prompt,
        helmet_prompt=helmet_prompt,
        jacket_prompt=jacket_prompt,
        suit_prompt=suit_prompt,
        glove_prompt=glove_prompt,
        boot_prompt=boot_prompt,
    )
