from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile

import database as db
from collage import get_or_build_brand_collage, get_or_build_color_collage
from keyboards import (
    BackCallback,
    HelmetBrandCallback, HelmetColorCallback, HelmetModelCallback,
    MenuCallback, brands_keyboard, helmet_colors_keyboard,
    helmet_models_keyboard, main_menu_keyboard,
)
from states import HelmetStates, OnboardingStates
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
        reply_markup=brands_keyboard(brands, HelmetBrandCallback, cancel_entity="helmet"),
        parse_mode="HTML",
    )


@router.callback_query(HelmetBrandCallback.filter(), HelmetStates.choosing_brand)
async def on_helmet_brand(query: CallbackQuery, callback_data: HelmetBrandCallback, state: FSMContext):
    await query.answer()
    brand = callback_data.brand

    collage_path = await get_or_build_brand_collage("helmet", brand)
    helmets = await db.get_helmet_models(brand)

    await state.update_data(brand=brand)
    await state.set_state(HelmetStates.choosing_model)
    await query.message.delete()

    photo_msg = await query.message.answer_photo(photo=FSInputFile(collage_path))
    text_msg = await query.message.answer(
        f"🪖 <b>{brand}</b> — выберите модель:",
        reply_markup=helmet_models_keyboard(helmets),
        parse_mode="HTML",
    )
    await state.update_data(collage_msg_id=photo_msg.message_id, menu_msg_id=text_msg.message_id)


@router.callback_query(BackCallback.filter((F.entity == "helmet") & (F.step == "to_brand")), HelmetStates.choosing_model)
async def on_helmet_back_to_brand(query: CallbackQuery, state: FSMContext):
    await query.answer()
    data = await state.get_data()

    collage_msg_id = data.get("collage_msg_id")
    if collage_msg_id:
        try:
            await query.bot.delete_message(query.message.chat.id, collage_msg_id)
        except Exception:
            pass

    brands = await db.get_helmet_brands()
    await state.set_state(HelmetStates.choosing_brand)
    await query.message.edit_text(
        "🪖 <b>Выберите бренд шлема:</b>",
        reply_markup=brands_keyboard(brands, HelmetBrandCallback, cancel_entity="helmet"),
        parse_mode="HTML",
    )


@router.callback_query(HelmetModelCallback.filter(), HelmetStates.choosing_model)
async def on_helmet_model(query: CallbackQuery, callback_data: HelmetModelCallback, state: FSMContext):
    await query.answer()

    data = await state.get_data()
    brand = data.get("brand", "")

    helmets = await db.get_helmet_models(brand)
    helmet = next((h for h in helmets if h.id == callback_data.helmet_id), None)
    model_name = helmet.model if helmet else ""

    colors = await db.get_helmet_colors(callback_data.helmet_id)

    await state.update_data(helmet_id=callback_data.helmet_id)
    await state.set_state(HelmetStates.choosing_color)

    collage_msg_id = data.get("collage_msg_id")
    if collage_msg_id:
        await query.bot.delete_message(query.message.chat.id, collage_msg_id)

    color_collage_path = await get_or_build_color_collage(
        "helmet", brand, callback_data.helmet_id, model_name
    )
    await query.message.delete()

    photo_msg = await query.message.answer_photo(photo=FSInputFile(color_collage_path))
    text_msg = await query.message.answer(
        "🎨 Выберите расцветку:",
        reply_markup=helmet_colors_keyboard(colors, callback_data.helmet_id),
        parse_mode="HTML",
    )
    await state.update_data(collage_msg_id=photo_msg.message_id, menu_msg_id=text_msg.message_id)


@router.callback_query(BackCallback.filter((F.entity == "helmet") & (F.step == "to_model")), HelmetStates.choosing_color)
async def on_helmet_back_to_model(query: CallbackQuery, state: FSMContext):
    await query.answer()
    data = await state.get_data()
    brand = data.get("brand", "")

    collage_msg_id = data.get("collage_msg_id")
    if collage_msg_id:
        try:
            await query.bot.delete_message(query.message.chat.id, collage_msg_id)
        except Exception:
            pass

    helmets = await db.get_helmet_models(brand)
    collage_path = await get_or_build_brand_collage("helmet", brand)

    await state.set_state(HelmetStates.choosing_model)
    await query.message.delete()

    photo_msg = await query.message.answer_photo(photo=FSInputFile(collage_path))
    text_msg = await query.message.answer(
        f"🪖 <b>{brand}</b> — выберите модель:",
        reply_markup=helmet_models_keyboard(helmets),
        parse_mode="HTML",
    )
    await state.update_data(collage_msg_id=photo_msg.message_id, menu_msg_id=text_msg.message_id)


@router.callback_query(HelmetColorCallback.filter(), HelmetStates.choosing_color)
async def on_helmet_color(query: CallbackQuery, callback_data: HelmetColorCallback, state: FSMContext):
    helmet_file = await db.get_helmet_file(callback_data.helmet_id, callback_data.color_id)
    if not helmet_file:
        await query.answer("❌ Фото для этой комбинации не найдено.", show_alert=True)
        return

    await query.answer()
    await db.update_user_helmet_file(query.from_user.id, helmet_file.id)

    data = await state.get_data()
    collage_msg_id = data.get("collage_msg_id")
    if collage_msg_id:
        await query.bot.delete_message(query.message.chat.id, collage_msg_id)

    user = await db.get_user_by_tg_id(query.from_user.id)
    onboarding = data.get("onboarding", False)

    if onboarding:
        from handlers.start import show_onboarding_equip_screen
        await show_onboarding_equip_screen(query, state)
    else:
        await state.clear()
        await query.message.edit_text(
            config_text(user),
            reply_markup=main_menu_keyboard(
                has_bike=user.bike_file_id is not None,
                has_helmet=True,
                has_jacket=user.jacket_file_id is not None,
                has_suit=user.suit_file_id is not None,
                has_glove=user.glove_file_id is not None,
                has_boot=user.boot_file_id is not None,
                has_photos=photoset_is_complete(user.photoset),
            ),
            parse_mode="HTML",
        )




@router.callback_query(BackCallback.filter((F.entity == "helmet") & (F.step == "to_menu")), HelmetStates.choosing_brand)
async def on_helmet_cancel(query: CallbackQuery, state: FSMContext):
    await query.answer()
    data = await state.get_data()
    onboarding = data.get("onboarding", False)
    if onboarding:
        await state.set_state(OnboardingStates.after_bike)
        await state.update_data(onboarding=True)
        from handlers.start import show_onboarding_equip_screen
        await show_onboarding_equip_screen(query, state)
    else:
        from handlers.start import send_main_menu
        user = await db.get_user_by_tg_id(query.from_user.id)
        await send_main_menu(query.message, user, state)

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
            has_jacket=user.jacket_file_id is not None,
            has_suit=user.suit_file_id is not None,
            has_glove=user.glove_file_id is not None,
            has_boot=user.boot_file_id is not None,
            has_photos=photoset_is_complete(user.photoset),
        ),
        parse_mode="HTML",
    )
