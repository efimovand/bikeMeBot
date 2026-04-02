import database as db


async def make_final_prompt(
    bike_file_id: int,
    helmet_file_id: int | None = None,
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

    # --- Финальный промпт ---
    helmet_photo_mention = "and additional photo of a motorcycle helmet." if has_helmet else ""

    default = await db.get_default_prompt()
    final_prompt = default.text.format(
        helmet_photo_mention=helmet_photo_mention,
        bike_prompt=bike_prompt,
        location_prompt=location_prompt,
        helmet_prompt=helmet_prompt,
    )

    return final_prompt
