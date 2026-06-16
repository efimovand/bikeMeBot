import asyncio
import html
import logging
from pathlib import Path
import aiohttp
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message
from config import settings
import database as db
from handlers.start import send_main_menu
from handlers.admin import notify_admins
from kie_ai import generate_for_user, InsufficientCreditsError, ContentPolicyError
from keyboards import MenuCallback, generate_again_keyboard, no_balance_keyboard, NoBalanceCallback
from utils import safe_delete
from prompts import make_final_prompt
from utils import _config_msg_ids


logger = logging.getLogger(__name__)

router = Router()
BASE = Path(settings.media_dir)
TEST_MEDIA_BASE = Path(__file__).resolve().parent.parent / "media"  # TODO: убрать после тестов

ESTIMATED_SECONDS = 180
LOADER_INTERVAL = 6
BAR_LENGTH = 10

# Транзиентные сетевые ошибки (таймаут соединения к kie.ai и т.п.) ретраим
# молча, без списания и без сообщений юзеру. Лоадер при этом продолжает крутиться.
MAX_TRANSIENT_RETRIES = 2
TRANSIENT_RETRY_DELAY = 3  # секунд между попытками

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
        "Анализируем образ...",
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


def _admin_generation_summary(user, tg_id: int, is_new: bool) -> str:
    """Краткая сводка о генерации для уведомления админам."""
    bf = user.bike_file
    bike = f"{bf.bike.brand} {bf.bike.model} / {bf.color.name}" if bf else "—"
    loc = (user.location.description or user.location.name) if user.location else "по умолчанию"
    helmet = (
        f"{user.helmet_file.helmet.brand} {user.helmet_file.helmet.model} / {user.helmet_file.color.name}"
        if user.helmet_file else "—"
    )
    if user.jacket_file:
        body = (f"Куртка {user.jacket_file.jacket.brand} {user.jacket_file.jacket.model} "
                f"/ {user.jacket_file.color.name}")
    elif user.suit_file:
        body = (f"Комбинезон {user.suit_file.suit.brand} {user.suit_file.suit.model} "
                f"/ {user.suit_file.color.name}")
    else:
        body = "—"
    glove = (
        f"{user.glove_file.glove.brand} {user.glove_file.glove.model} / {user.glove_file.color.name}"
        if user.glove_file else "—"
    )
    boot = (
        f"{user.boot_file.boot.brand} {user.boot_file.boot.model} / {user.boot_file.color.name}"
        if user.boot_file else "—"
    )
    head = "🆕 <b>Новый пользователь</b>" if is_new else "👤 Пользователь"
    return (
        f"{head} <code>{tg_id}</code> сгенерировал 🖼\n\n"
        f"🏍 <b>Байк:</b> {bike}\n"
        f"📍 <b>Локация:</b> {loc}\n"
        f"🪖 <b>Шлем:</b> {helmet}\n"
        f"🧥 <b>Верх:</b> {body}\n"
        f"🧤 <b>Перчатки:</b> {glove}\n"
        f"🥾 <b>Ботинки:</b> {boot}"
    )


async def run_generation(message_or_query, tg_id: int):
    if tg_id in _active_generations:
        if not isinstance(message_or_query, Message):
            await message_or_query.answer("⏳ Генерация уже выполняется.", show_alert=True)
        return

    user = await db.get_user_by_tg_id(tg_id)

    # Защита от стейл-клавиатур: кнопка «Сгенерировать» могла прийти из старого
    # сообщения, когда байк/фото уже сброшены (или юзера нет в БД).
    if user is None or user.bike_file is None or not db.photoset_is_complete(user.photoset):
        text = (
            "⚠️ Для генерации нужны выбранный мотоцикл и загруженные фото.\n"
            "Отправьте /start и завершите настройку."
        )
        if isinstance(message_or_query, Message):
            await message_or_query.answer(text)
        else:
            await message_or_query.answer()
            await message_or_query.message.answer(text)
        return

    if user.balance <= 0:
        from database import get_catalog_counts
        counts = await get_catalog_counts()

        text = (
            "<b>Пора заправиться!</b> ⛽️\n\n"
            "Генерации закончились, но ваш экип ждет. После пополнения вам откроются:\n"
            f"🏍 Более <b>{counts['bikes']}</b> байков\n"
            f"🏁 Полный каталог экипировки (<b>{sum(counts.values()) - counts['bikes']}+</b> позиций)\n\n"
            "<i>Жмите кнопку ниже, чтобы продолжить подбор.</i>"
        )

        if isinstance(message_or_query, Message):
            await message_or_query.answer(text, reply_markup=no_balance_keyboard(), parse_mode="HTML")
        else:
            await message_or_query.answer()
            await message_or_query.message.answer(text, reply_markup=no_balance_keyboard(), parse_mode="HTML")
        return

    # Всё после add — под try/finally: если что-то упадёт до начала генерации
    # (make_final_prompt, отправка сообщения), юзер не должен остаться
    # заблокированным в _active_generations до рестарта бота.
    _active_generations.add(tg_id)
    try:
        if isinstance(message_or_query, Message):
            target = message_or_query
        else:
            try:
                await message_or_query.message.delete()
            except Exception:
                pass
            _config_msg_ids.pop(tg_id, None)
            target = message_or_query.message

        prompt = await make_final_prompt(user)

        # TODO: убрать после тестов (промпт + пути)
        # if tg_id == 370377802:
        if False:
            prompt += '\n\nPhoto format: 1:1 square'
            if len(prompt) <= 4080:
                await target.answer(f"<code>{prompt}</code>", parse_mode="HTML")
            else:
                half = len(prompt) // 2
                part_1 = prompt[:half]
                part_2 = prompt[half:]
                await target.answer(f"<code>{part_1}</code>", parse_mode="HTML")
                await target.answer(f"<code>{part_2}</code>", parse_mode="HTML")
            paths = get_paths(user)
            joined = " ".join(f'"{p}"' for p in paths)
            if len(joined) <= 259:
                await target.answer(f"<code>{joined}</code>", parse_mode="HTML", reply_markup=generate_again_keyboard())
            else:
                chunks = split_into_chunks(paths)
                for i, chunk in enumerate(chunks):
                    kb = generate_again_keyboard() if i == len(chunks) - 1 else None
                    await target.answer(f"<code>{' '.join(chunk)}</code>", parse_mode="HTML", reply_markup=kb)
            await db.decrement_balance(tg_id)

        else:
            waiting_msg = await target.answer(
                "⏳ <b>Генерация началась!</b>\n\n"
                f"[{'░' * BAR_LENGTH}] 0%\n"
                "<i>Загружаем фото...</i>",
                parse_mode="HTML",
            )

            stop_event = asyncio.Event()
            loader_task = asyncio.create_task(_run_loader(waiting_msg, stop_event))
            waiting_msg_alive = True
            is_new_user = await db.count_generations_for_user(user.id) == 0
            transient_retries = 0

            try:
                while True:
                    account = await db.get_active_account()
                    if account is None:
                        stop_event.set()
                        loader_task.cancel()
                        await waiting_msg.edit_text("❌ Нет доступных аккаунтов для генерации. Попробуйте позже.")
                        try:
                            await notify_admins(
                                target.bot,
                                "🚨 Нет активных аккаунтов KIE.ai — генерации остановлены "
                                f"(запросил <code>{tg_id}</code>).",
                            )
                        except Exception:
                            pass
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

                        await db.decrement_balance(tg_id)

                        await waiting_msg.delete()
                        waiting_msg_alive = False
                        await target.answer_photo(
                            FSInputFile(result_path),
                            caption="🏍 Готово!",
                            reply_markup=generate_again_keyboard(),
                        )
                        try:
                            await notify_admins(
                                target.bot,
                                _admin_generation_summary(user, tg_id, is_new_user),
                                exclude_tg_id=tg_id,
                            )
                        except Exception:
                            pass
                        return

                    except InsufficientCreditsError:
                        await db.update_generation_status(generation.id, "failed")
                        await db.deactivate_account(account.id)

                    except ContentPolicyError:
                        stop_event.set()
                        loader_task.cancel()
                        await db.update_generation_status(generation.id, "failed")
                        await waiting_msg.edit_text("❌ Изображение не прошло проверку контента.")
                        return

                    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                        # Транзиентная сетевая ошибка (таймаут соединения к kie.ai и т.п.).
                        # Молча ретраим без списания: юзеру ничего не пишем, лоадер крутится дальше.
                        await db.update_generation_status(generation.id, "failed")
                        transient_retries += 1
                        logger.warning(
                            "Transient network error on generation #%s (attempt %d/%d) for tg_id=%s: %s",
                            generation.id, transient_retries, MAX_TRANSIENT_RETRIES, tg_id, e,
                        )
                        if transient_retries <= MAX_TRANSIENT_RETRIES:
                            await asyncio.sleep(TRANSIENT_RETRY_DELAY)
                            continue
                        # Ретраи исчерпаны — ведём себя как при обычной ошибке.
                        stop_event.set()
                        loader_task.cancel()
                        try:
                            await notify_admins(
                                target.bot,
                                f"🚨 Генерация #{generation.id} не удалась после "
                                f"{MAX_TRANSIENT_RETRIES} сетевых ретраев, "
                                f"пользователь <code>{tg_id}</code>:\n"
                                f"<pre>{html.escape(str(e)[:1500])}</pre>",
                            )
                        except Exception:
                            pass
                        error_text = (
                            "❌ Не получилось сгенерировать изображение. "
                            "Попробуйте ещё раз чуть позже — генерация не списана."
                        )
                        try:
                            if waiting_msg_alive:
                                await waiting_msg.edit_text(error_text)
                            else:
                                await target.answer(error_text)
                        except Exception:
                            pass
                        return

                    except Exception as e:
                        stop_event.set()
                        loader_task.cancel()
                        await db.update_generation_status(generation.id, "failed")
                        # Детали ошибки — админам, юзеру — нейтральный текст
                        # (в исключении бывают сырые ответы API и URL-ы).
                        try:
                            await notify_admins(
                                target.bot,
                                f"🚨 Ошибка генерации #{generation.id}, "
                                f"пользователь <code>{tg_id}</code>:\n"
                                f"<pre>{html.escape(str(e)[:1500])}</pre>",
                            )
                        except Exception:
                            pass
                        error_text = (
                            "❌ Не получилось сгенерировать изображение. "
                            "Попробуйте ещё раз чуть позже — генерация не списана."
                        )
                        try:
                            if waiting_msg_alive:
                                await waiting_msg.edit_text(error_text)
                            else:
                                await target.answer(error_text)
                        except Exception:
                            pass
                        raise
            finally:
                # Страховка: лоадер не должен пережить генерацию,
                # даже если исключение прилетело вне внутреннего try
                # (например, из db.create_generation).
                stop_event.set()
                loader_task.cancel()
    finally:
        _active_generations.discard(tg_id)


@router.callback_query(MenuCallback.filter(F.action == "generate"))
async def on_generate(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await run_generation(query, query.from_user.id)


@router.callback_query(MenuCallback.filter(F.action == "topup"))
async def on_topup(query: CallbackQuery, state: FSMContext):
    await query.answer()
    from handlers.payment import show_topup_screen
    await show_topup_screen(query)


@router.callback_query(MenuCallback.filter(F.action == "main_menu"))
async def on_main_menu(query: CallbackQuery, state: FSMContext):
    await query.answer()
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    user = await db.get_user_by_tg_id(query.from_user.id)
    await send_main_menu(query.message, user, state)


@router.callback_query(NoBalanceCallback.filter(F.action == "topup"))
async def on_no_balance_topup(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await safe_delete(query.message)
    from handlers.payment import show_topup_screen
    await show_topup_screen(query)


@router.callback_query(NoBalanceCallback.filter(F.action == "cancel"))
async def on_no_balance_cancel(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await safe_delete(query.message)
