from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile

import database as db
from collage import get_or_build_brand_collage, get_or_build_color_collage
from keyboards import (
    BackCallback,
    BootBrandCallback, BootColorCallback, BootModelCallback,
    MenuCallback, brands_keyboard, boot_colors_keyboard,
    boot_models_keyboard, main_menu_keyboard,
)
from states import BootStates, OnboardingStates
from utils import config_text
from database import photoset_is_complete


router = Router()


@router.callback_query(MenuCallback.filter(F.action == "boot"))
async def on_boot_menu(query: CallbackQuery, state: FSMContext):
    await query.answer()
    brands = await db.get_boot_brands()
    await state.set_state(BootStates.choosing_brand)
    await query.message.edit_text(
        "🥾 <b>Выберите бренд ботинок:</b>",
        reply_markup=brands_keyboard(brands, BootBrandCallback, cancel_entity="boot"),
        parse_mode="HTML",
    )


@router.callback_query(BootBrandCallback.filter(), BootStates.choosing_brand)
async def on_boot_brand(query: CallbackQuery, callback_data: BootBrandCallback, state: FSMContext):
    await query.answer()
    brand = callback_data.brand

    collage_path = await get_or_build_brand_collage("boot", brand)
    boots = await db.get_boot_models(brand)

    await state.update_data(brand=brand)
    await state.set_state(BootStates.choosing_model)
    await query.message.delete()

    photo_msg = await query.message.answer_photo(photo=FSInputFile(collage_path))
    text_msg = await query.message.answer(
        f"🥾 <b>{brand}</b> — выберите модель:",
        reply_markup=boot_models_keyboard(boots),
        parse_mode="HTML",
    )
    await state.update_data(collage_msg_id=photo_msg.message_id, menu_msg_id=text_msg.message_id)


@router.callback_query(BackCallback.filter((F.entity == "boot") & (F.step == "to_brand")), BootStates.choosing_model)
async def on_boot_back_to_brand(query: CallbackQuery, state: FSMContext):
    await query.answer()
    data = await state.get_data()

    collage_msg_id = data.get("collage_msg_id")
    if collage_msg_id:
        try:
            await query.bot.delete_message(query.message.chat.id, collage_msg_id)
        except Exception:
            pass

    brands = await db.get_boot_brands()
    await state.set_state(BootStates.choosing_brand)
    await query.message.edit_text(
        "🥾 <b>Выберите бренд ботинок:</b>",
        reply_markup=brands_keyboard(brands, BootBrandCallback, cancel_entity="boot"),
        parse_mode="HTML",
    )


@router.callback_query(BootModelCallback.filter(), BootStates.choosing_model)
async def on_boot_model(query: CallbackQuery, callback_data: BootModelCallback, state: FSMContext):
    await query.answer()

    data = await state.get_data()
    brand = data.get("brand", "")

    boots = await db.get_boot_models(brand)
    boot = next((b for b in boots if b.id == callback_data.boot_id), None)
    model_name = boot.model if boot else ""

    colors = await db.get_boot_colors(callback_data.boot_id)

    await state.update_data(boot_id=callback_data.boot_id)
    await state.set_state(BootStates.choosing_color)

    collage_msg_id = data.get("collage_msg_id")
    if collage_msg_id:
        await query.bot.delete_message(query.message.chat.id, collage_msg_id)

    color_collage_path = await get_or_build_color_collage(
        "boot", brand, callback_data.boot_id, model_name
    )
    await query.message.delete()

    photo_msg = await query.message.answer_photo(photo=FSInputFile(color_collage_path))
    text_msg = await query.message.answer(
        "🎨 Выберите расцветку:",
        reply_markup=boot_colors_keyboard(colors, callback_data.boot_id),
        parse_mode="HTML",
    )
    await state.update_data(collage_msg_id=photo_msg.message_id, menu_msg_id=text_msg.message_id)


@router.callback_query(BackCallback.filter((F.entity == "boot") & (F.step == "to_model")), BootStates.choosing_color)
async def on_boot_back_to_model(query: CallbackQuery, state: FSMContext):
    await query.answer()
    data = await state.get_data()
    brand = data.get("brand", "")

    collage_msg_id = data.get("collage_msg_id")
    if collage_msg_id:
        try:
            await query.bot.delete_message(query.message.chat.id, collage_msg_id)
        except Exception:
            pass

    boots = await db.get_boot_models(brand)
    collage_path = await get_or_build_brand_collage("boot", brand)

    await state.set_state(BootStates.choosing_model)
    await query.message.delete()

    photo_msg = await query.message.answer_photo(photo=FSInputFile(collage_path))
    text_msg = await query.message.answer(
        f"🥾 <b>{brand}</b> — выберите модель:",
        reply_markup=boot_models_keyboard(boots),
        parse_mode="HTML",
    )
    await state.update_data(collage_msg_id=photo_msg.message_id, menu_msg_id=text_msg.message_id)


@router.callback_query(BootColorCallback.filter(), BootStates.choosing_color)
async def on_boot_color(query: CallbackQuery, callback_data: BootColorCallback, state: FSMContext):
    boot_file = await db.get_boot_file(callback_data.boot_id, callback_data.color_id)
    if not boot_file:
        await query.answer("❌ Фото для этой комбинации не найдено.", show_alert=True)
        return

    await query.answer()
    await db.update_user_boot_file(query.from_user.id, boot_file.id)

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
                has_helmet=user.helmet_file_id is not None,
                has_jacket=user.jacket_file_id is not None,
                has_suit=user.suit_file_id is not None,
                has_glove=user.glove_file_id is not None,
                has_boot=True,
                has_photos=photoset_is_complete(user.photoset),
            ),
            parse_mode="HTML",
        )




@router.callback_query(BackCallback.filter((F.entity == "boot") & (F.step == "to_menu")), BootStates.choosing_brand)
async def on_boot_cancel(query: CallbackQuery, state: FSMContext):
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

@router.callback_query(MenuCallback.filter(F.action == "boot_remove"))
async def on_boot_remove(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await db.clear_user_boot_file(query.from_user.id)
    user = await db.get_user_by_tg_id(query.from_user.id)
    await query.message.edit_text(
        config_text(user),
        reply_markup=main_menu_keyboard(
            has_bike=user.bike_file_id is not None,
            has_helmet=user.helmet_file_id is not None,
            has_jacket=user.jacket_file_id is not None,
            has_suit=user.suit_file_id is not None,
            has_glove=user.glove_file_id is not None,
            has_boot=False,
            has_photos=photoset_is_complete(user.photoset),
        ),
        parse_mode="HTML",
    )
