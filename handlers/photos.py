from pathlib import Path
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, FSInputFile
import database as db
from config import settings
from keyboards import MenuCallback, main_menu_keyboard
from states import PhotoStates
from utils import config_text


router = Router()
EXAMPLES_DIR = Path(settings.media_dir) / "examples" / "photoset"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


async def _delete_chain(bot: Bot, chat_id: int, msg_ids: list[int]) -> None:
    for msg_id in msg_ids:
        try:
            await bot.delete_message(chat_id, msg_id)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Вход в загрузку фото (из главного меню)
# ---------------------------------------------------------------------------

async def start_photo_upload(query: CallbackQuery, state: FSMContext) -> None:
    """Универсальный старт загрузки фото: удаляет текущее сообщение, шлёт текст + пример."""
    await state.set_state(PhotoStates.waiting_front)
    try:
        await query.message.delete()
    except Exception:
        pass

    text_msg = await query.message.answer(
        "📸 <b>Шаг 1 из 3 — Фото анфас</b>\n\n"
        "Сфотографируйся прямо, смотри в камеру, лицо и плечи должны быть хорошо видны.\n\n"
        "Отправь фото 👇",
        parse_mode="HTML",
    )
    example_msg = await query.message.answer_photo(
        photo=FSInputFile(EXAMPLES_DIR / "front.jpg"),
        caption="Пример фото",
    )
    await state.update_data(chain_msg_ids=[text_msg.message_id, example_msg.message_id])


@router.callback_query(MenuCallback.filter(F.action == "photos"))
async def on_photos_menu(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await start_photo_upload(query, state)


# ---------------------------------------------------------------------------
# Приём фото
# ---------------------------------------------------------------------------

@router.message(PhotoStates.waiting_front, F.photo)
async def got_front_photo(message: Message, state: FSMContext, bot: Bot):
    path = await save_photo(bot, message, "front.jpg")
    data = await state.get_data()
    chain_ids: list[int] = data.get("chain_msg_ids", [])

    await state.update_data(front_photo=path)
    await state.set_state(PhotoStates.waiting_side)

    text_msg = await message.answer(
        "✅ Фото анфас сохранено!\n\n"
        "📸 <b>Шаг 2 из 3 — Фото в профиль</b>\n\n"
        "Встань боком к камере (левым или правым — неважно).\n\n"
        "Отправь фото 👇",
        parse_mode="HTML",
    )
    example_msg = await message.answer_photo(
        photo=FSInputFile(EXAMPLES_DIR / "side.jpg"),
        caption="Пример фото",
    )
    chain_ids += [message.message_id, text_msg.message_id, example_msg.message_id]
    await state.update_data(chain_msg_ids=chain_ids)


@router.message(PhotoStates.waiting_side, F.photo)
async def got_side_photo(message: Message, state: FSMContext, bot: Bot):
    path = await save_photo(bot, message, "side.jpg")
    data = await state.get_data()
    chain_ids: list[int] = data.get("chain_msg_ids", [])

    await state.update_data(side_photo=path)
    await state.set_state(PhotoStates.waiting_body)

    text_msg = await message.answer(
        "✅ Фото в профиль сохранено!\n\n"
        "📸 <b>Шаг 3 из 3 — Фото в полный рост</b>\n\n"
        "Встань прямо, в кадре должно быть видно тебя от головы до ног.\n\n"
        "Отправь фото 👇",
        parse_mode="HTML",
    )
    example_msg = await message.answer_photo(
        photo=FSInputFile(EXAMPLES_DIR / "body.jpg"),
        caption="Пример фото",
    )
    chain_ids += [message.message_id, text_msg.message_id, example_msg.message_id]
    await state.update_data(chain_msg_ids=chain_ids)


@router.message(PhotoStates.waiting_body, F.photo)
async def got_body_photo(message: Message, state: FSMContext, bot: Bot):
    path = await save_photo(bot, message, "body.jpg")
    data = await state.get_data()
    onboarding = data.get("onboarding", False)
    chain_ids: list[int] = data.get("chain_msg_ids", [])
    chain_ids.append(message.message_id)

    user = await db.get_user_by_tg_id(message.from_user.id)
    await db.upsert_user_photoset(
        user_id=user.id,
        front_photo=data["front_photo"],
        side_photo=data["side_photo"],
        body_photo=path,
    )
    await state.clear()

    await _delete_chain(bot, message.chat.id, chain_ids)

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
                has_suit=user.suit_file_id is not None,
                has_glove=user.glove_file_id is not None,
                has_boot=user.boot_file_id is not None,
                has_photos=True,
            ),
            parse_mode="HTML",
        )


# ---------------------------------------------------------------------------
# Если прислали не фото
# ---------------------------------------------------------------------------

@router.message(PhotoStates.waiting_front)
@router.message(PhotoStates.waiting_side)
@router.message(PhotoStates.waiting_body)
async def wrong_input_during_photos(message: Message):
    await message.answer("📸 Пожалуйста, отправь именно <b>фотографию</b>.", parse_mode="HTML")