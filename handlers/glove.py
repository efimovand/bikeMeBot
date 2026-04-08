from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile

import database as db
from collage import get_or_build_brand_collage, get_or_build_color_collage
from keyboards import (
    GloveBrandCallback, GloveColorCallback, GloveModelCallback,
    MenuCallback, brands_keyboard, glove_colors_keyboard,
    glove_models_keyboard, main_menu_keyboard,
)
from states import GloveStates, PhotoStates
from utils import config_text
from database import photoset_is_complete


router = Router()


@router.callback_query(MenuCallback.filter(F.action == "glove"))
async def on_glove_menu(query: CallbackQuery, state: FSMContext):
    await query.answer()
    brands = await db.get_glove_brands()
    await state.set_state(GloveStates.choosing_brand)
    await query.message.edit_text(
        "🧤 <b>Выберите бренд перчаток:</b>",
        reply_markup=brands_keyboard(brands, GloveBrandCallback),
        parse_mode="HTML",
    )


@router.callback_query(GloveBrandCallback.filter(), GloveStates.choosing_brand)
async def on_glove_brand(query: CallbackQuery, callback_data: GloveBrandCallback, state: FSMContext):
    await query.answer()
    brand = callback_data.brand

    collage_path = await get_or_build_brand_collage("glove", brand)
    gloves = await db.get_glove_models(brand)

    await state.update_data(brand=brand)
    await state.set_state(GloveStates.choosing_model)
    await query.message.delete()

    photo_msg = await query.message.answer_photo(photo=FSInputFile(collage_path))
    text_msg = await query.message.answer(
        f"🧤 <b>{brand}</b> — выберите модель:",
        reply_markup=glove_models_keyboard(gloves),
        parse_mode="HTML",
    )
    await state.update_data(collage_msg_id=photo_msg.message_id, menu_msg_id=text_msg.message_id)


@router.callback_query(GloveModelCallback.filter(), GloveStates.choosing_model)
async def on_glove_model(query: CallbackQuery, callback_data: GloveModelCallback, state: FSMContext):
    await query.answer()

    data = await state.get_data()
    brand = data.get("brand", "")

    gloves = await db.get_glove_models(brand)
    glove = next((g for g in gloves if g.id == callback_data.glove_id), None)
    model_name = glove.model if glove else ""

    colors = await db.get_glove_colors(callback_data.glove_id)

    await state.update_data(glove_id=callback_data.glove_id)
    await state.set_state(GloveStates.choosing_color)

    collage_msg_id = data.get("collage_msg_id")
    if collage_msg_id:
        await query.bot.delete_message(query.message.chat.id, collage_msg_id)

    color_collage_path = await get_or_build_color_collage(
        "glove", brand, callback_data.glove_id, model_name
    )
    await query.message.delete()

    photo_msg = await query.message.answer_photo(photo=FSInputFile(color_collage_path))
    text_msg = await query.message.answer(
        "🎨 Выберите расцветку:",
        reply_markup=glove_colors_keyboard(colors, callback_data.glove_id),
        parse_mode="HTML",
    )
    await state.update_data(collage_msg_id=photo_msg.message_id, menu_msg_id=text_msg.message_id)


@router.callback_query(GloveColorCallback.filter(), GloveStates.choosing_color)
async def on_glove_color(query: CallbackQuery, callback_data: GloveColorCallback, state: FSMContext):
    glove_file = await db.get_glove_file(callback_data.glove_id, callback_data.color_id)
    if not glove_file:
        await query.answer("❌ Фото для этой комбинации не найдено.", show_alert=True)
        return

    await query.answer()
    await db.update_user_glove_file(query.from_user.id, glove_file.id)

    data = await state.get_data()
    collage_msg_id = data.get("collage_msg_id")
    if collage_msg_id:
        await query.bot.delete_message(query.message.chat.id, collage_msg_id)

    user = await db.get_user_by_tg_id(query.from_user.id)
    onboarding = data.get("onboarding", False)

    if onboarding:
        await state.set_state(PhotoStates.waiting_front)
        await query.message.edit_text(
            f"✅ Перчатки выбраны: <b>{glove_file.glove.brand} {glove_file.glove.model} / {glove_file.color.name}</b>\n\n"
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
                has_suit=user.suit_file_id is not None,
                has_glove=True,
                has_boot=user.boot_file_id is not None,
                has_photos=photoset_is_complete(user.photoset),
            ),
            parse_mode="HTML",
        )


@router.callback_query(MenuCallback.filter(F.action == "glove_remove"))
async def on_glove_remove(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await db.clear_user_glove_file(query.from_user.id)
    user = await db.get_user_by_tg_id(query.from_user.id)
    await query.message.edit_text(
        config_text(user),
        reply_markup=main_menu_keyboard(
            has_bike=user.bike_file_id is not None,
            has_helmet=user.helmet_file_id is not None,
            has_jacket=user.jacket_file_id is not None,
            has_suit=user.suit_file_id is not None,
            has_glove=False,
            has_boot=user.boot_file_id is not None,
            has_photos=photoset_is_complete(user.photoset),
        ),
        parse_mode="HTML",
    )