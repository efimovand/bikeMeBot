import database as db


async def make_final_prompt(
    bike_file_id: int,
    helmet_file_id: int | None = None,
    jacket_file_id: int | None = None,
    glove_file_id: int | None = None,
) -> str:
    # --- Байк + локация ---
    bike_file = await db.get_bike_file_by_id(bike_file_id)
    raw_bike_prompt = bike_file.bike.prompt
    location_prompt = bike_file.bike.location.prompt

    bike_prompt = f"Motorcycle ergonomics and scale: {raw_bike_prompt}" if raw_bike_prompt else ""

    # --- Шлем (опционально) ---
    has_helmet = helmet_file_id is not None
    helmet_prompt = "IMPORTANT: The person must be shown without any helmet, with their head completely bare." if not has_helmet else ""
    if has_helmet:
        helmet_file = await db.get_helmet_file_by_id(helmet_file_id)
        raw_helmet_prompt = helmet_file.helmet.prompt
        helmet_dict_prompts = await db.get_prompts_by_type("helmet")
        helmet_dict_text = helmet_dict_prompts[0].text
        helmet_prompt = helmet_dict_text.format(helmet_prompt=raw_helmet_prompt) if raw_helmet_prompt else helmet_dict_text.format(helmet_prompt="")

    # --- Куртка (опционально) ---
    has_jacket = jacket_file_id is not None
    jacket_prompt = "IMPORTANT: The person must be shown without a motorcycle jacket, in their own clothing." if not has_jacket else ""
    if has_jacket:
        jacket_file = await db.get_jacket_file_by_id(jacket_file_id)
        raw_jacket_prompt = jacket_file.jacket.prompt
        jacket_dict_prompts = await db.get_prompts_by_type("jacket")
        jacket_dict_text = jacket_dict_prompts[0].text
        jacket_prompt = jacket_dict_text.format(jacket_prompt=raw_jacket_prompt) if raw_jacket_prompt else jacket_dict_text.format(jacket_prompt="")

    # --- Перчатки (опционально) ---
    has_glove = glove_file_id is not None
    glove_prompt = "IMPORTANT: The person must be shown without motorcycle gloves, bare hands." if not has_glove else ""
    if has_glove:
        glove_file = await db.get_glove_file_by_id(glove_file_id)
        raw_glove_prompt = glove_file.glove.prompt
        glove_dict_prompts = await db.get_prompts_by_type("glove")
        glove_dict_text = glove_dict_prompts[0].text
        glove_prompt = glove_dict_text.format(glove_prompt=raw_glove_prompt) if raw_glove_prompt else glove_dict_text.format(glove_prompt="")

    # --- Финальный промпт ---
    helmet_photo_mention = ", a photo of a motorcycle helmet" if has_helmet else ""
    jacket_photo_mention = ", a photo of a motorcycle jacket" if has_jacket else ""
    glove_photo_mention = ", a photo of motorcycle gloves" if has_glove else ""

    default = await db.get_default_prompt()
    final_prompt = default.text.format(
        helmet_photo_mention=helmet_photo_mention,
        jacket_photo_mention=jacket_photo_mention,
        glove_photo_mention=glove_photo_mention,
        bike_prompt=bike_prompt,
        location_prompt=location_prompt,
        helmet_prompt=helmet_prompt,
        jacket_prompt=jacket_prompt,
        glove_prompt=glove_prompt,
    )

    return final_prompt
