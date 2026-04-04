from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile
import database as db
from collage import get_or_build_collage
from keyboards import (
    JacketBrandCallback, JacketColorCallback, JacketModelCallback,
    MenuCallback, brands_keyboard, jacket_colors_keyboard,
    jacket_models_keyboard, main_menu_keyboard,
)
from states import JacketStates, PhotoStates
from utils import config_text
from database import photoset_is_complete


router = Router()


@router.callback_query(MenuCallback.filter(F.action == "jacket"))
async def on_jacket_menu(query: CallbackQuery, state: FSMContext):
    await query.answer()
    brands = await db.get_jacket_brands()

    await state.set_state(JacketStates.choosing_brand)
    await query.message.edit_text(
        "🧥 <b>Выберите бренд куртки:</b>",
        reply_markup=brands_keyboard(brands, JacketBrandCallback),
        parse_mode="HTML",
    )


@router.callback_query(JacketBrandCallback.filter(), JacketStates.choosing_brand)
async def on_jacket_brand(query: CallbackQuery, callback_data: JacketBrandCallback, state: FSMContext):
    await query.answer()
    brand = callback_data.brand

    collage_path = await get_or_build_collage("jacket", brand)
    jackets = await db.get_jacket_models(brand)

    await state.update_data(brand=brand)
    await state.set_state(JacketStates.choosing_model)

    await query.message.delete()

    photo_msg = await query.message.answer_photo(photo=FSInputFile(collage_path))
    text_msg = await query.message.answer(
        f"🧥 <b>{brand}</b> — выберите модель:",
        reply_markup=jacket_models_keyboard(jackets),
        parse_mode="HTML",
    )

    await state.update_data(collage_msg_id=photo_msg.message_id, menu_msg_id=text_msg.message_id)


@router.callback_query(JacketModelCallback.filter(), JacketStates.choosing_model)
async def on_jacket_model(query: CallbackQuery, callback_data: JacketModelCallback, state: FSMContext):
    await query.answer()
    colors = await db.get_jacket_colors(callback_data.jacket_id)

    await state.update_data(jacket_id=callback_data.jacket_id)
    await state.set_state(JacketStates.choosing_color)

    data = await state.get_data()
    collage_msg_id = data.get("collage_msg_id")
    if collage_msg_id:
        await query.bot.delete_message(query.message.chat.id, collage_msg_id)

    await query.message.edit_text(
        "🎨 Выберите расцветку:",
        reply_markup=jacket_colors_keyboard(colors, callback_data.jacket_id),
        parse_mode="HTML",
    )


@router.callback_query(JacketColorCallback.filter(), JacketStates.choosing_color)
async def on_jacket_color(query: CallbackQuery, callback_data: JacketColorCallback, state: FSMContext):
    jacket_file = await db.get_jacket_file(callback_data.jacket_id, callback_data.color_id)
    if not jacket_file:
        await query.answer("❌ Фото для этой комбинации не найдено.", show_alert=True)
        return

    await query.answer()
    await db.update_user_jacket_file(query.from_user.id, jacket_file.id)

    user = await db.get_user_by_tg_id(query.from_user.id)
    data = await state.get_data()
    onboarding = data.get("onboarding", False)

    if onboarding:
        await state.set_state(PhotoStates.waiting_front)
        await query.message.edit_text(
            f"✅ Куртка выбрана: <b>{jacket_file.jacket.brand} {jacket_file.jacket.model} / {jacket_file.color.name}</b>\n\n"
            "📸 <b>Шаг 1 из 3 — Фото анфас</b>\n\n"
            "Сфотографируйся прямо, смотри в камеру, лицо и плечи должны быть хорошо видны.\n\n"
            "Отправь фото 👇",
            parse_mode="HTML",
        )
    else:
        await state.clear()
        await query.message.edit_text(
            config_text(user),
            reply_markup=main_menu_keyboard(
                has_bike=user.bike_file_id is not None,
                has_helmet=user.helmet_file_id is not None,
                has_jacket=True,
                has_photos=photoset_is_complete(user.photoset),
            ),
            parse_mode="HTML",
        )


@router.callback_query(MenuCallback.filter(F.action == "jacket_remove"))
async def on_jacket_remove(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await db.clear_user_jacket_file(query.from_user.id)
    user = await db.get_user_by_tg_id(query.from_user.id)
    await query.message.edit_text(
        config_text(user),
        reply_markup=main_menu_keyboard(
            has_bike=user.bike_file_id is not None,
            has_helmet=user.helmet_file_id is not None,
            has_jacket=False,
            has_photos=photoset_is_complete(user.photoset),
        ),
        parse_mode="HTML",
    )
