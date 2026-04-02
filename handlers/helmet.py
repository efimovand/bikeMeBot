from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import database as db
from keyboards import (
    HelmetBrandCallback, HelmetColorCallback, HelmetModelCallback,
    MenuCallback, brands_keyboard, helmet_colors_keyboard,
    helmet_models_keyboard, main_menu_keyboard,
)
from states import HelmetStates, PhotoStates
from utils import config_text
from database import photoset_is_complete

router = Router()


@router.callback_query(MenuCallback.filter(F.action == "helmet"))
async def on_helmet_menu(query: CallbackQuery, state: FSMContext):
    await query.answer()
    brands = await db.get_helmet_brands()

    await state.set_state(HelmetStates.choosing_brand)
    await query.message.edit_text(
        "🪖 <b>Выберите бренд шлема:</b>",
        reply_markup=brands_keyboard(brands, HelmetBrandCallback),
        parse_mode="HTML",
    )


@router.callback_query(HelmetBrandCallback.filter(), HelmetStates.choosing_brand)
async def on_helmet_brand(query: CallbackQuery, callback_data: HelmetBrandCallback, state: FSMContext):
    await query.answer()
    helmets = await db.get_helmet_models(callback_data.brand)

    await state.update_data(brand=callback_data.brand)
    await state.set_state(HelmetStates.choosing_model)
    await query.message.edit_text(
        f"🪖 <b>{callback_data.brand}</b> — выберите модель:",
        reply_markup=helmet_models_keyboard(helmets),
        parse_mode="HTML",
    )


@router.callback_query(HelmetModelCallback.filter(), HelmetStates.choosing_model)
async def on_helmet_model(query: CallbackQuery, callback_data: HelmetModelCallback, state: FSMContext):
    await query.answer()
    colors = await db.get_helmet_colors(callback_data.helmet_id)

    await state.update_data(helmet_id=callback_data.helmet_id)
    await state.set_state(HelmetStates.choosing_color)
    await query.message.edit_text(
        "🎨 Выберите расцветку шлема:",
        reply_markup=helmet_colors_keyboard(colors, callback_data.helmet_id),
        parse_mode="HTML",
    )


@router.callback_query(HelmetColorCallback.filter(), HelmetStates.choosing_color)
async def on_helmet_color(query: CallbackQuery, callback_data: HelmetColorCallback, state: FSMContext):
    helmet_file = await db.get_helmet_file(callback_data.helmet_id, callback_data.color_id)
    if not helmet_file:
        await query.answer("❌ Фото для этой комбинации не найдено.", show_alert=True)
        return

    await query.answer()

    await db.update_user_helmet_file(query.from_user.id, helmet_file.id)

    user = await db.get_user_by_tg_id(query.from_user.id)
    data = await state.get_data()
    onboarding = data.get("onboarding", False)

    if onboarding:
        # Онбординг: после шлема сразу переходим к загрузке фото
        await state.set_state(PhotoStates.waiting_front)
        await query.message.edit_text(
            f"✅ Мотоцикл выбран: <b>{user.bike_file.bike.brand} {user.bike_file.bike.model} / {user.bike_file.color.name}</b>\n"
            f"✅ Шлем выбран: <b>{helmet_file.helmet.brand} {helmet_file.helmet.model} / {helmet_file.color.name}</b>\n\n"
            "📸 <b>Шаг 1 из 3 — Фото анфас</b>\n\n"
            "Сфотографируйся прямо, смотри в камеру, лицо и плечи должны быть хорошо видны.\n\n"
            "Отправь фото 👇",
            parse_mode="HTML",
        )
    else:
        # Обычный режим — главное меню
        await state.clear()
        await query.message.edit_text(
            config_text(user),
            reply_markup=main_menu_keyboard(
                has_bike=user.bike_file_id is not None,
                has_helmet=True,
                has_photos=photoset_is_complete(user.photoset),
            ),
            parse_mode="HTML",
        )


@router.callback_query(MenuCallback.filter(F.action == "helmet_remove"))
async def on_helmet_remove(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await db.clear_user_helmet_file(query.from_user.id)
    user = await db.get_user_by_tg_id(query.from_user.id)
    await query.message.edit_text(
        config_text(user),
        reply_markup=main_menu_keyboard(
            has_bike=user.bike_file_id is not None,
            has_helmet=False,
            has_photos=photoset_is_complete(user.photoset),
        ),
        parse_mode="HTML",
    )
