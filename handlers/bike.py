from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import database as db
from keyboards import (
    BikeBrandCallback, BikeColorCallback, BikeModelCallback,
    MenuCallback, OnboardingContinueCallback,
    after_bike_onboarding_keyboard, bike_colors_keyboard,
    bike_models_keyboard, brands_keyboard, main_menu_keyboard,
)
from states import BikeStates, OnboardingStates
from utils import config_text
from database import photoset_is_complete

router = Router()


@router.callback_query(MenuCallback.filter(F.action == "bike"))
async def on_bike_menu(query: CallbackQuery, state: FSMContext):
    await query.answer()
    brands = await db.get_bike_brands()

    await state.set_state(BikeStates.choosing_brand)
    await query.message.edit_text(
        "🏍 <b>Выберите бренд мотоцикла:</b>",
        reply_markup=brands_keyboard(brands, BikeBrandCallback),
        parse_mode="HTML",
    )


@router.callback_query(BikeBrandCallback.filter(), BikeStates.choosing_brand)
async def on_bike_brand(query: CallbackQuery, callback_data: BikeBrandCallback, state: FSMContext):
    await query.answer()
    bikes = await db.get_bike_models(callback_data.brand)

    await state.update_data(brand=callback_data.brand)
    await state.set_state(BikeStates.choosing_model)
    await query.message.edit_text(
        f"🏍 <b>{callback_data.brand}</b> — выберите модель:",
        reply_markup=bike_models_keyboard(bikes),
        parse_mode="HTML",
    )


@router.callback_query(BikeModelCallback.filter(), BikeStates.choosing_model)
async def on_bike_model(query: CallbackQuery, callback_data: BikeModelCallback, state: FSMContext):
    await query.answer()
    colors = await db.get_bike_colors(callback_data.bike_id)

    await state.update_data(bike_id=callback_data.bike_id)
    await state.set_state(BikeStates.choosing_color)
    await query.message.edit_text(
        "🎨 Выберите расцветку:",
        reply_markup=bike_colors_keyboard(colors, callback_data.bike_id),
        parse_mode="HTML",
    )


@router.callback_query(BikeColorCallback.filter(), BikeStates.choosing_color)
async def on_bike_color(query: CallbackQuery, callback_data: BikeColorCallback, state: FSMContext):
    bike_file = await db.get_bike_file(callback_data.bike_id, callback_data.color_id)
    if not bike_file:
        await query.answer("❌ Фото для этой комбинации не найдено.", show_alert=True)
        return

    await query.answer()

    await db.update_user_bike_file(query.from_user.id, bike_file.id)

    data = await state.get_data()
    onboarding = data.get("onboarding", False)

    if onboarding:
        await state.set_state(OnboardingStates.after_bike)
        await query.message.edit_text(
            f"✅ Мотоцикл выбран: <b>{bike_file.bike.brand} {bike_file.bike.model} / {bike_file.color.name}</b>\n\n"
            "Если хотите, можете добавить шлем, куртку и другую экипировку.",
            reply_markup=after_bike_onboarding_keyboard(),
            parse_mode="HTML",
        )
    else:
        # Обычный режим (редактирование): возвращаем в главное меню
        user = await db.get_user_by_tg_id(query.from_user.id)
        await state.clear()
        await query.message.edit_text(
            config_text(user),
            reply_markup=main_menu_keyboard(
                has_bike=True,
                has_helmet=user.helmet_file_id is not None,
                has_jacket=user.jacket_file_id is not None,
                has_photos=photoset_is_complete(user.photoset),
            ),
            parse_mode="HTML",
        )