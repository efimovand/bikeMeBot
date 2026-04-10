from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import database as db
from config import load_invited_users
from keyboards import (
    BikeBrandCallback,
    HelmetBrandCallback,
    JacketBrandCallback,
    OnboardingContinueCallback,
    PolicyCallback,
    brands_keyboard,
    main_menu_keyboard,
    policy_keyboard,
)
from states import BikeStates, HelmetStates, JacketStates, OnboardingStates, PhotoStates
from utils import config_text, _config_msg_ids


router = Router()

INVITED_BONUS = 50
_bonus_pending: set[int] = set()


async def send_main_menu(message_or_query, user, state: FSMContext):
    """Универсальная отправка главного меню. Всегда в единственном экземпляре."""
    await state.clear()

    text = config_text(user)
    keyboard = main_menu_keyboard(
        has_bike=user.bike_file_id is not None,
        has_helmet=user.helmet_file_id is not None,
        has_jacket=user.jacket_file_id is not None,
        has_suit=user.suit_file_id is not None,
        has_glove=user.glove_file_id is not None,
        has_boot=user.boot_file_id is not None,
        has_photos=db.photoset_is_complete(user.photoset),
    )

    tg_id = user.tg_id

    if isinstance(message_or_query, Message):
        answer_target = message_or_query
    else:
        answer_target = message_or_query.message

    if tg_id in _bonus_pending:
        _bonus_pending.discard(tg_id)
        await answer_target.answer(
            f"🎉 Вы находитесь в списке приглашённых пользователей.\n\n"
            f"Вам на баланс начислено ⭐️ {INVITED_BONUS} генераций.\n\n"
            f"Приятного использования!",
        )

    if isinstance(message_or_query, Message):
        old_msg_id = _config_msg_ids.pop(tg_id, None)
        if old_msg_id:
            try:
                await message_or_query.bot.delete_message(message_or_query.chat.id, old_msg_id)
            except Exception:
                pass

        sent = await message_or_query.answer(text, reply_markup=keyboard, parse_mode="HTML")
        _config_msg_ids[tg_id] = sent.message_id
    else:
        await message_or_query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        _config_msg_ids[tg_id] = message_or_query.message.message_id


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    if message.from_user.id != 370377802:  # TODO: Дебаг
        await message.answer('Вам недоступен функционал BikeMeBot. Обратитесь к @efimov_and')
        return

    user, created = await db.get_or_create_user(
        tg_id=message.from_user.id,
        name=message.from_user.full_name,
    )

    if not created:
        await send_main_menu(message, user, state)
        return

    if message.from_user.id in load_invited_users():
        await db.add_balance(message.from_user.id, INVITED_BONUS)
        _bonus_pending.add(message.from_user.id)

    await state.set_state(OnboardingStates.waiting_policy)
    await message.answer(
        (
            "👋 Привет! Это <b>MotoMe</b> — бот, который примерит на тебя любой мотоцикл и экип.\n\n"
            "Как это работает:\n"
            "1. Выбираешь байк и цвет\n"
            "2. Выбираешь экипировку (по желанию)\n"
            "3. Загружаешь 3 своих фото\n"
            "4. ИИ генерирует фото, где ты уже на этом байке 🔥\n\n"
            "Нажимая кнопку ниже, ты соглашаешься с политикой обработки данных."
        ),
        reply_markup=policy_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(PolicyCallback.filter(F.action == "agree"), OnboardingStates.waiting_policy)
async def policy_agreed(query: CallbackQuery, state: FSMContext):
    await query.answer()

    await query.message.edit_reply_markup(reply_markup=None)

    brands = await db.get_bike_brands()
    await state.update_data(onboarding=True)
    await state.set_state(BikeStates.choosing_brand)

    await query.message.answer(
        "✅ Отлично! Давай выберем твой мотоцикл.\n\n"
        "🏍 <b>Выберите бренд:</b>",
        reply_markup=brands_keyboard(brands, BikeBrandCallback),
        parse_mode="HTML",
    )


@router.callback_query(OnboardingContinueCallback.filter(F.action == "helmet"), OnboardingStates.after_bike)
async def onboarding_add_helmet(query: CallbackQuery, state: FSMContext):
    await query.answer()

    brands = await db.get_helmet_brands()
    await state.update_data(onboarding=True)
    await state.set_state(HelmetStates.choosing_brand)

    await query.message.edit_text(
        "🪖 <b>Выберите бренд шлема:</b>",
        reply_markup=brands_keyboard(brands, HelmetBrandCallback),
        parse_mode="HTML",
    )


@router.callback_query(OnboardingContinueCallback.filter(F.action == "jacket"), OnboardingStates.after_bike)
async def onboarding_add_jacket(query: CallbackQuery, state: FSMContext):
    await query.answer()

    brands = await db.get_jacket_brands()
    await state.update_data(onboarding=True)
    await state.set_state(JacketStates.choosing_brand)

    await query.message.edit_text(
        "🧥 <b>Выберите бренд куртки:</b>",
        reply_markup=brands_keyboard(brands, JacketBrandCallback),
        parse_mode="HTML",
    )


@router.callback_query(OnboardingContinueCallback.filter(F.action == "photos"), OnboardingStates.after_bike)
async def onboarding_go_photos(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.update_data(onboarding=True)
    await state.set_state(PhotoStates.waiting_front)

    await query.message.edit_text(
        "📸 <b>Шаг 1 из 3 — Фото анфас</b>\n\n"
        "Сфотографируйся прямо, смотри в камеру, лицо и плечи должны быть хорошо видны.\n\n"
        "Отправь фото 👇",
        parse_mode="HTML",
    )