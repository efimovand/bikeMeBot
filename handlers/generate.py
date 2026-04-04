from pathlib import Path
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message
from config import settings
import database as db
from handlers.start import send_main_menu
from kie_ai import generate_for_user, InsufficientCreditsError, ContentPolicyError
from keyboards import MenuCallback, generate_again_keyboard
from prompts import make_final_prompt


router = Router()
BASE = Path(settings.media_dir)

TEST_MEDIA_BASE = Path("C:/Users/masha/Desktop/bikeMeBot/media/")  # TODO: убрать после тестов


async def run_generation(message_or_query, tg_id: int):
    if isinstance(message_or_query, Message):
        target = message_or_query
    else:
        await message_or_query.answer()
        target = message_or_query.message

    user = await db.get_user_by_tg_id(tg_id)

    prompt = await make_final_prompt(
        bike_file_id=user.bike_file_id,
        helmet_file_id=user.helmet_file_id,
        jacket_file_id=user.jacket_file_id,
        glove_file_id=user.glove_file_id,
    )

    # TODO: убрать после тестов (промпт)
    await target.answer(f"<code>{prompt}</code>", parse_mode="HTML")

    # TODO: убрать после тестов (пути до файлов)
    bike_path = TEST_MEDIA_BASE / user.bike_file.file
    paths = [str(bike_path)]
    if user.helmet_file:
        helmet_path = TEST_MEDIA_BASE / user.helmet_file.file
        paths.append(str(helmet_path))
    if user.jacket_file:
        jacket_path = TEST_MEDIA_BASE / user.jacket_file.file
        paths.append(str(jacket_path))
    paths_text = "\n".join(f"<code>{p}</code>" for p in paths)
    await target.answer(paths_text, parse_mode="HTML")

    # waiting_msg = await target.answer("⏳ Генерация началась, подожди немного...", parse_mode="HTML")
    #
    # while True:
    #     account = await db.get_active_account()
    #     if account is None:
    #         await waiting_msg.edit_text("❌ Нет доступных аккаунтов для генерации.")
    #         return
    #
    #     generation = await db.create_generation(
    #         user_id=user.id,
    #         account_id=account.id,
    #         bike_file=user.bike_file,
    #         helmet_file_id=user.helmet_file_id,
    #         jacket_file_id=user.jacket_file_id,
    #     )
    #
    #     try:
    #         result_path = await generate_for_user(
    #             generation_id=generation.id,
    #             tg_id=tg_id,
    #             api_key=account.token,
    #             bike_file_path=BASE / user.bike_file.file,
    #             helmet_file_path=BASE / user.helmet_file.file if user.helmet_file else None,
    #             jacket_file_path=BASE / user.jacket_file.file if user.jacket_file else None,
    #             glove_file_path=BASE / user.glove_file.file if user.glove_file else None,
    #             prompt=prompt,
    #         )
    #
    #         await db.update_generation_status(generation.id, "success")
    #         await db.increment_spent_stars(tg_id)
    #
    #         await waiting_msg.delete()
    #         await target.answer_photo(
    #             FSInputFile(result_path),
    #             caption="🏍 Готово!",
    #             reply_markup=generate_again_keyboard(),
    #         )
    #         return
    #
    #     except InsufficientCreditsError:
    #         await db.update_generation_status(generation.id, "failed")
    #         await db.deactivate_account(account.id)
    #
    #     except ContentPolicyError:
    #         await db.update_generation_status(generation.id, "failed")
    #
    #     except Exception as e:
    #         await db.update_generation_status(generation.id, "failed")
    #         await waiting_msg.edit_text(f"❌ Ошибка генерации: {e}")
    #         raise


@router.callback_query(MenuCallback.filter(F.action == "generate"))
async def on_generate(query: CallbackQuery, state: FSMContext):
    await run_generation(query, query.from_user.id)


@router.callback_query(MenuCallback.filter(F.action == "main_menu"))
async def on_main_menu(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await query.message.edit_reply_markup(reply_markup=None)
    user = await db.get_user_by_tg_id(query.from_user.id)
    await send_main_menu(query.message, user, state)
