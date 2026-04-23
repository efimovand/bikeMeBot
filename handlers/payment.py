from aiogram import F, Router
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData

import database as db

router = Router()

# ---------------------------------------------------------------------------
# Пакеты: (stars, generations, label)
# ---------------------------------------------------------------------------

PACKAGES = [
    (50,   1,   "⭐️ 50 — 1 генерация"),
    (150,  5,   "⭐️ 150 — 5 генераций  (−40%)"),
    (450,  20,  "⭐️ 450 — 20 генераций (−55%)"),
    (1750, 100, "⭐️ 1750 — 100 генераций (−65%)"),
]


class TopupCallback(CallbackData, prefix="topup_pkg"):
    stars: int
    generations: int


# ---------------------------------------------------------------------------
# Клавиатура выбора пакета
# ---------------------------------------------------------------------------

def topup_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for stars, gens, label in PACKAGES:
        builder.button(
            text=label,
            callback_data=TopupCallback(stars=stars, generations=gens),
        )
    builder.adjust(1)
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Показать экран пополнения
# ---------------------------------------------------------------------------

async def show_topup_screen(target: Message | CallbackQuery) -> None:
    msg = target if isinstance(target, Message) else target.message
    await msg.answer(
        "⭐️ <b>Выберите количество генераций:</b>",
        reply_markup=topup_keyboard(),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Нажатие на пакет → отправляем инвойс
# ---------------------------------------------------------------------------

@router.callback_query(TopupCallback.filter())
async def on_topup_package(query: CallbackQuery, callback_data: TopupCallback):
    await query.answer()
    gens = callback_data.generations
    stars = callback_data.stars

    plural = (
        "генерацию" if gens == 1
        else "генерации" if 2 <= gens <= 4
        else "генераций"
    )

    await query.message.answer_invoice(
        title=f"{gens} {plural}",
        description=f"Пополнение баланса на {gens} {plural} в BikeMe",
        payload=f"topup:{stars}:{gens}",
        currency="XTR",
        prices=[LabeledPrice(label=f"{gens} {plural}", amount=stars)],
    )


# ---------------------------------------------------------------------------
# Pre-checkout — всегда подтверждаем
# ---------------------------------------------------------------------------

@router.pre_checkout_query()
async def on_pre_checkout(pre_checkout: PreCheckoutQuery):
    await pre_checkout.answer(ok=True)


# ---------------------------------------------------------------------------
# Успешная оплата → зачислить генерации
# ---------------------------------------------------------------------------

@router.message(F.successful_payment)
async def on_successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    try:
        _, stars_str, gens_str = payload.split(":")
        stars = int(stars_str)
        gens = int(gens_str)
    except ValueError:
        return

    await db.add_balance(message.from_user.id, gens)
    await db.add_spent_stars(message.from_user.id, stars)

    plural = (
        "генерация" if gens == 1
        else "генерации" if 2 <= gens <= 4
        else "генераций"
    )
    new_balance = await db.get_user_by_tg_id(message.from_user.id)

    await message.answer(
        f"✅ Оплата прошла успешно!\n\n"
        f"Начислено: <b>{gens} {plural}</b>\n"
        f"Текущий баланс: <b>{new_balance.balance} ⭐️</b>",
        parse_mode="HTML",
    )