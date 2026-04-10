import asyncio
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
from utils import _config_msg_ids


router = Router()
BASE = Path(settings.media_dir)
TEST_MEDIA_BASE = Path("C:/Users/masha/Desktop/bikeMeBot/media/")  # TODO: убрать после тестов

ESTIMATED_SECONDS = 80
LOADER_INTERVAL = 6
BAR_LENGTH = 10

_active_generations: set[int] = set()


# TODO: убрать после тестов
def get_paths(user) -> list[str]:
    files = [
        user.bike_file,
        user.helmet_file,
        user.jacket_file or user.suit_file,
        user.glove_file,
        user.boot_file,
    ]
    return [str(TEST_MEDIA_BASE / f.file) for f in files if f]


# TODO: убрать после тестов
def split_into_chunks(paths: list[str], limit: int = 259) -> list[list[str]]:
    chunks, current, current_len = [], [], 0
    for p in paths:
        entry = f'"{p}"'
        needed = len(entry) + (1 if current else 0)
        if current and current_len + needed > limit:
            chunks.append(current)
            current, current_len = [entry], len(entry)
        else:
            current.append(entry)
            current_len += needed
    if current:
        chunks.append(current)
    return chunks


async def _run_loader(message, stop_event: asyncio.Event):
    start = asyncio.get_event_loop().time()
    stages = [
        "Загружаем фото...",
        "Анализирем образ...",
        "Подбираем ракурс...",
        "Рисуем детали...",
        "Финальные штрихи...",
    ]
    while not stop_event.is_set():
        await asyncio.sleep(LOADER_INTERVAL)
        if stop_event.is_set():
            break
        elapsed = asyncio.get_event_loop().time() - start
        progress = min(elapsed / ESTIMATED_SECONDS, 0.95)
        filled = round(progress * BAR_LENGTH)
        bar = "█" * filled + "░" * (BAR_LENGTH - filled)
        percent = int(progress * 100)
        stage = stages[min(int(progress * len(stages)), len(stages) - 1)]
        try:
            await message.edit_text(
                f"⏳ <b>Генерация началась!</b>\n\n"
                f"[{bar}] {percent}%\n"
                f"<i>{stage}</i>",
                parse_mode="HTML",
            )
        except Exception:
            break


async def _show_topup_stub(target, tg_id: int) -> None:
    """Заглушка для экрана оплаты (пока не реализована)."""
    await target.answer(
        "⭐️ <b>Пополнение баланса</b>\n\n"
        "У вас закончились генерации. Чтобы продолжить, пополните баланс.\n\n"
        "<i>Скоро здесь появится возможность оплаты — следите за обновлениями!</i>",
        parse_mode="HTML",
    )


async def run_generation(message_or_query, tg_id: int):
    if tg_id in _active_generations:
        if not isinstance(message_or_query, Message):
            await message_or_query.answer("⏳ Генерация уже выполняется.", show_alert=True)
        return

    user = await db.get_user_by_tg_id(tg_id)
    if user.balance <= 0:
        if isinstance(message_or_query, Message):
            await _show_topup_stub(message_or_query, tg_id)
        else:
            await message_or_query.answer()
            await _show_topup_stub(message_or_query.message, tg_id)
        return

    _active_generations.add(tg_id)
    if isinstance(message_or_query, Message):
        target = message_or_query
    else:
        try:
            await message_or_query.message.delete()
        except Exception:
            pass
        _config_msg_ids.pop(tg_id, None)
        target = message_or_query.message

    user = await db.get_user_by_tg_id(tg_id)

    prompt = await make_final_prompt(
        bike_file_id=user.bike_file_id,
        location_id=user.location_id,
        helmet_file_id=user.helmet_file_id,
        jacket_file_id=user.jacket_file_id,
        suit_file_id=user.suit_file_id,
        glove_file_id=user.glove_file_id,
        boot_file_id=user.boot_file_id,
    )

    # # TODO: убрать после тестов (промпт + пути)
    # await target.answer(f"<code>{prompt}</code>", parse_mode="HTML")
    # paths = get_paths(user)
    # joined = " ".join(f'"{p}"' for p in paths)
    # if len(joined) <= 259:
    #     await target.answer(f"<code>{joined}</code>", parse_mode="HTML", reply_markup=generate_again_keyboard())
    # else:
    #     chunks = split_into_chunks(paths)
    #     for i, chunk in enumerate(chunks):
    #         kb = generate_again_keyboard() if i == len(chunks) - 1 else None
    #         await target.answer(f"<code>{' '.join(chunk)}</code>", parse_mode="HTML", reply_markup=kb)

    waiting_msg = await target.answer(
        "⏳ <b>Генерация началась!</b>\n\n"
        f"[{'░' * BAR_LENGTH}] 0%\n"
        "<i>Загружаем фото...</i>",
        parse_mode="HTML",
    )

    stop_event = asyncio.Event()
    loader_task = asyncio.create_task(_run_loader(waiting_msg, stop_event))

    try:
        while True:
            account = await db.get_active_account()
            if account is None:
                stop_event.set()
                loader_task.cancel()
                await waiting_msg.edit_text("❌ Нет доступных аккаунтов для генерации.")
                return

            generation = await db.create_generation(
                user_id=user.id,
                account_id=account.id,
                bike_file=user.bike_file,
                helmet_file_id=user.helmet_file_id,
                jacket_file_id=user.jacket_file_id,
                suit_file_id=user.suit_file_id,
                glove_file_id=user.glove_file_id,
                boot_file_id=user.boot_file_id,
            )

            try:
                result_path = await generate_for_user(
                    generation_id=generation.id,
                    tg_id=tg_id,
                    api_key=account.token,
                    bike_file_path=BASE / user.bike_file.file,
                    helmet_file_path=BASE / user.helmet_file.file if user.helmet_file else None,
                    jacket_file_path=BASE / user.jacket_file.file if user.jacket_file else None,
                    suit_file_path=BASE / user.suit_file.file if user.suit_file else None,
                    glove_file_path=BASE / user.glove_file.file if user.glove_file else None,
                    boot_file_path=BASE / user.boot_file.file if user.boot_file else None,
                    prompt=prompt,
                )

                stop_event.set()
                loader_task.cancel()
                await db.update_generation_status(generation.id, "success")

                # Списываем 1 генерацию с баланса (внутри также +1 к spent_stars)
                await db.decrement_balance(tg_id)

                await waiting_msg.delete()
                await target.answer_photo(
                    FSInputFile(result_path),
                    caption="🏍 Готово!",
                    reply_markup=generate_again_keyboard(),
                )
                return

            except InsufficientCreditsError:
                await db.update_generation_status(generation.id, "failed")
                await db.deactivate_account(account.id)
                # продолжаем цикл — пробуем следующий аккаунт

            except ContentPolicyError:
                stop_event.set()
                loader_task.cancel()
                await db.update_generation_status(generation.id, "failed")
                await waiting_msg.edit_text("❌ Изображение не прошло проверку контента.")
                return

            except Exception as e:
                stop_event.set()
                loader_task.cancel()
                await db.update_generation_status(generation.id, "failed")
                await waiting_msg.edit_text(f"❌ Ошибка генерации: {e}")
                raise
    finally:
        _active_generations.discard(tg_id)


@router.callback_query(MenuCallback.filter(F.action == "generate"))
async def on_generate(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await run_generation(query, query.from_user.id)


@router.callback_query(MenuCallback.filter(F.action == "topup"))
async def on_topup(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await _show_topup_stub(query.message, query.from_user.id)


@router.callback_query(MenuCallback.filter(F.action == "main_menu"))
async def on_main_menu(query: CallbackQuery, state: FSMContext):
    await query.answer()
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    user = await db.get_user_by_tg_id(query.from_user.id)
    await send_main_menu(query.message, user, state)