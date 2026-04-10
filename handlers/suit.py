from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile

import database as db
from collage import get_or_build_brand_collage, get_or_build_color_collage
from keyboards import (
    SuitBrandCallback, SuitColorCallback, SuitModelCallback,
    MenuCallback, brands_keyboard, suit_colors_keyboard,
    suit_models_keyboard, main_menu_keyboard,
)
from states import SuitStates, PhotoStates
from utils import config_text
from database import photoset_is_complete


router = Router()


@router.callback_query(MenuCallback.filter(F.action == "suit"))
async def on_suit_menu(query: CallbackQuery, state: FSMContext):
    await query.answer()
    brands = await db.get_suit_brands()
    user = await db.get_user_by_tg_id(query.from_user.id)

    warning = ""
    if user.jacket_file_id is not None:
        warning = "❗ <i>Комбинезон заменит выбранную куртку.</i>\n\n"

    await state.set_state(SuitStates.choosing_brand)
    await query.message.edit_text(
        f"{warning}🏁 <b>Выберите бренд комбинезона:</b>",
        reply_markup=brands_keyboard(brands, SuitBrandCallback),
        parse_mode="HTML",
    )


@router.callback_query(SuitBrandCallback.filter(), SuitStates.choosing_brand)
async def on_suit_brand(query: CallbackQuery, callback_data: SuitBrandCallback, state: FSMContext):
    await query.answer()
    brand = callback_data.brand

    collage_path = await get_or_build_brand_collage("suit", brand)
    suits = await db.get_suit_models(brand)

    await state.update_data(brand=brand)
    await state.set_state(SuitStates.choosing_model)
    await query.message.delete()

    photo_msg = await query.message.answer_photo(photo=FSInputFile(collage_path))
    text_msg = await query.message.answer(
        f"🏁 <b>{brand}</b> — выберите модель:",
        reply_markup=suit_models_keyboard(suits),
        parse_mode="HTML",
    )
    await state.update_data(collage_msg_id=photo_msg.message_id, menu_msg_id=text_msg.message_id)


@router.callback_query(SuitModelCallback.filter(), SuitStates.choosing_model)
async def on_suit_model(query: CallbackQuery, callback_data: SuitModelCallback, state: FSMContext):
    await query.answer()

    data = await state.get_data()
    brand = data.get("brand", "")

    suits = await db.get_suit_models(brand)
    suit = next((s for s in suits if s.id == callback_data.suit_id), None)
    model_name = suit.model if suit else ""

    colors = await db.get_suit_colors(callback_data.suit_id)

    await state.update_data(suit_id=callback_data.suit_id)
    await state.set_state(SuitStates.choosing_color)

    collage_msg_id = data.get("collage_msg_id")
    if collage_msg_id:
        await query.bot.delete_message(query.message.chat.id, collage_msg_id)

    color_collage_path = await get_or_build_color_collage(
        "suit", brand, callback_data.suit_id, model_name
    )
    await query.message.delete()

    photo_msg = await query.message.answer_photo(photo=FSInputFile(color_collage_path))
    text_msg = await query.message.answer(
        "🎨 Выберите расцветку:",
        reply_markup=suit_colors_keyboard(colors, callback_data.suit_id),
        parse_mode="HTML",
    )
    await state.update_data(collage_msg_id=photo_msg.message_id, menu_msg_id=text_msg.message_id)


@router.callback_query(SuitColorCallback.filter(), SuitStates.choosing_color)
async def on_suit_color(query: CallbackQuery, callback_data: SuitColorCallback, state: FSMContext):
    suit_file = await db.get_suit_file(callback_data.suit_id, callback_data.color_id)
    if not suit_file:
        await query.answer("❌ Фото для этой комбинации не найдено.", show_alert=True)
        return

    await query.answer()
    await db.update_user_suit_file(query.from_user.id, suit_file.id)

    data = await state.get_data()
    collage_msg_id = data.get("collage_msg_id")
    if collage_msg_id:
        await query.bot.delete_message(query.message.chat.id, collage_msg_id)

    user = await db.get_user_by_tg_id(query.from_user.id)
    onboarding = data.get("onboarding", False)

    if onboarding:
        await state.set_state(PhotoStates.waiting_front)
        await query.message.edit_text(
            f"✅ Комбинезон выбран: <b>{suit_file.suit.brand} {suit_file.suit.model} / {suit_file.color.name}</b>\n\n"
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
                has_jacket=user.jacket_file_id is not None,
                has_suit=True,
                has_glove=user.glove_file_id is not None,
                has_boot=user.boot_file_id is not None,
                has_photos=photoset_is_complete(user.photoset),
            ),
            parse_mode="HTML",
        )


@router.callback_query(MenuCallback.filter(F.action == "suit_remove"))
async def on_suit_remove(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await db.clear_user_suit_file(query.from_user.id)
    user = await db.get_user_by_tg_id(query.from_user.id)
    await query.message.edit_text(
        config_text(user),
        reply_markup=main_menu_keyboard(
            has_bike=user.bike_file_id is not None,
            has_helmet=user.helmet_file_id is not None,
            has_jacket=user.jacket_file_id is not None,
            has_suit=False,
            has_glove=user.glove_file_id is not None,
            has_boot=user.boot_file_id is not None,
            has_photos=photoset_is_complete(user.photoset),
        ),
        parse_mode="HTML",
    )