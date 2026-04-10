from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import database as db
from keyboards import LocationCallback, LocationResetCallback, MenuCallback, locations_keyboard, main_menu_keyboard
from states import LocationStates
from utils import config_text
from database import photoset_is_complete

router = Router()


@router.callback_query(MenuCallback.filter(F.action == "location"))
async def on_location_menu(query: CallbackQuery, state: FSMContext):
    await query.answer()
    locations = await db.get_all_locations()

    await state.set_state(LocationStates.choosing_location)
    await query.message.edit_text(
        "📍 <b>Выберите локацию:</b>\n\n"
        "<i>Локация по умолчанию соответствует стилю выбранного мотоцикла.</i>",
        reply_markup=locations_keyboard(locations),
        parse_mode="HTML",
    )


@router.callback_query(LocationResetCallback.filter(), LocationStates.choosing_location)
async def on_location_reset(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await db.clear_user_location(query.from_user.id)

    user = await db.get_user_by_tg_id(query.from_user.id)
    await state.clear()
    await query.message.edit_text(
        config_text(user),
        reply_markup=main_menu_keyboard(
            has_bike=user.bike_file_id is not None,
            has_helmet=user.helmet_file_id is not None,
            has_jacket=user.jacket_file_id is not None,
            has_suit=user.suit_file_id is not None,
            has_glove=user.glove_file_id is not None,
            has_boot=user.boot_file_id is not None,
            has_photos=photoset_is_complete(user.photoset),
        ),
        parse_mode="HTML",
    )


@router.callback_query(LocationCallback.filter(), LocationStates.choosing_location)
async def on_location_pick(query: CallbackQuery, callback_data: LocationCallback, state: FSMContext):
    await query.answer()
    await db.update_user_location(query.from_user.id, callback_data.location_id)

    user = await db.get_user_by_tg_id(query.from_user.id)
    await state.clear()
    await query.message.edit_text(
        config_text(user),
        reply_markup=main_menu_keyboard(
            has_bike=user.bike_file_id is not None,
            has_helmet=user.helmet_file_id is not None,
            has_jacket=user.jacket_file_id is not None,
            has_suit=user.suit_file_id is not None,
            has_glove=user.glove_file_id is not None,
            has_boot=user.boot_file_id is not None,
            has_photos=photoset_is_complete(user.photoset),
        ),
        parse_mode="HTML",
    )