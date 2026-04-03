from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import database as db
from config import settings
from keyboards import MenuCallback, main_menu_keyboard
from states import PhotoStates
from database import photoset_is_complete
from utils import config_text


router = Router()


def user_media_dir(tg_id: int) -> Path:
    path = settings.media_dir / "users" / str(tg_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def save_photo(bot: Bot, message: Message, filename: str) -> str:
    tg_id = message.from_user.id
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)

    save_dir = user_media_dir(tg_id)
    save_path = save_dir / filename
    await bot.download_file(file.file_path, destination=save_path)

    return str(Path("users") / str(tg_id) / filename)


# ---------------------------------------------------------------------------
# Вход в загрузку фото (из главного меню)
# ---------------------------------------------------------------------------

@router.callback_query(MenuCallback.filter(F.action == "photos"))
async def on_photos_menu(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.set_state(PhotoStates.waiting_front)
    await query.message.edit_text(
        "📸 <b>Шаг 1 из 3 — Фото анфас</b>\n\n"
        "Сфотографируйся прямо, смотри в камеру, лицо и плечи должны быть хорошо видны.\n\n"
        "Отправь фото 👇",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Приём фото
# ---------------------------------------------------------------------------

@router.message(PhotoStates.waiting_front, F.photo)
async def got_front_photo(message: Message, state: FSMContext, bot: Bot):
    path = await save_photo(bot, message, "front.jpg")
    await state.update_data(front_photo=path)
    await state.set_state(PhotoStates.waiting_side)

    await message.answer(
        "✅ Фото анфас сохранено!\n\n"
        "📸 <b>Шаг 2 из 3 — Фото в профиль</b>\n\n"
        "Встань боком к камере (левым или правым — неважно).\n\n"
        "Отправь фото 👇",
        parse_mode="HTML",
    )


@router.message(PhotoStates.waiting_side, F.photo)
async def got_side_photo(message: Message, state: FSMContext, bot: Bot):
    path = await save_photo(bot, message, "side.jpg")
    await state.update_data(side_photo=path)
    await state.set_state(PhotoStates.waiting_body)

    await message.answer(
        "✅ Фото в профиль сохранено!\n\n"
        "📸 <b>Шаг 3 из 3 — Фото в полный рост</b>\n\n"
        "Встань прямо, в кадре должно быть видно тебя от головы до ног.\n\n"
        "Отправь фото 👇",
        parse_mode="HTML",
    )


@router.message(PhotoStates.waiting_body, F.photo)
async def got_body_photo(message: Message, state: FSMContext, bot: Bot):
    path = await save_photo(bot, message, "body.jpg")
    data = await state.get_data()
    onboarding = data.get("onboarding", False)

    user = await db.get_user_by_tg_id(message.from_user.id)
    await db.upsert_user_photoset(
        user_id=user.id,
        front_photo=data["front_photo"],
        side_photo=data["side_photo"],
        body_photo=path,
    )
    await state.clear()

    if onboarding:
        from handlers.generate import run_generation
        await run_generation(message, message.from_user.id)
    else:
        user = await db.get_user_by_tg_id(message.from_user.id)
        await message.answer(
            "✅ Все три фото загружены!\n\n" + config_text(user),
            reply_markup=main_menu_keyboard(
                has_bike=user.bike_file_id is not None,
                has_helmet=user.helmet_file_id is not None,
                has_jacket=user.jacket_file_id is not None,
                has_photos=True,
            ),
            parse_mode="HTML",
        )


# ---------------------------------------------------------------------------
# Если прислали не фото во время ожидания
# ---------------------------------------------------------------------------

@router.message(PhotoStates.waiting_front)
@router.message(PhotoStates.waiting_side)
@router.message(PhotoStates.waiting_body)
async def wrong_input_during_photos(message: Message):
    await message.answer("📸 Пожалуйста, отправь именно <b>фотографию</b>.", parse_mode="HTML")