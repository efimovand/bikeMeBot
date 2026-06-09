import logging

from aiogram import F, Router
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
from handlers.admin import notify_admins

logger = logging.getLogger(__name__)
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

PAYMENT_PROBLEM_TEXT = (
    "⚠️ Оплата получена, но при начислении произошла ошибка.\n"
    "Администратор уже уведомлён и начислит генерации вручную."
)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message):
    sp = message.successful_payment
    tg_id = message.from_user.id
    charge_id = sp.telegram_payment_charge_id
    payload = sp.invoice_payload

    try:
        _, stars_str, gens_str = payload.split(":")
        stars = int(stars_str)
        gens = int(gens_str)
    except ValueError:
        # Деньги списаны, а сколько начислять — непонятно. Молчать нельзя:
        # сообщаем юзеру и зовём админов с charge_id для ручного начисления.
        logger.error("Bad invoice payload %r (charge_id=%s, tg_id=%s)", payload, charge_id, tg_id)
        await notify_admins(
            message.bot,
            "🚨 <b>Платёж с нераспознанным payload!</b>\n"
            f"Пользователь: <code>{tg_id}</code>\n"
            f"Сумма: {sp.total_amount} {sp.currency}\n"
            f"Payload: <code>{payload}</code>\n"
            f"charge_id: <code>{charge_id}</code>\n"
            "Начислите генерации вручную.",
        )
        await message.answer(PAYMENT_PROBLEM_TEXT)
        return

    try:
        new_balance = await db.apply_payment(tg_id, charge_id, stars, gens)
    except Exception:
        logger.exception("apply_payment failed (charge_id=%s, tg_id=%s)", charge_id, tg_id)
        await notify_admins(
            message.bot,
            "🚨 <b>Не удалось провести оплаченный платёж!</b>\n"
            f"Пользователь: <code>{tg_id}</code>\n"
            f"Пакет: {gens} генераций за {stars} ⭐️\n"
            f"charge_id: <code>{charge_id}</code>\n"
            "Начислите генерации вручную.",
        )
        await message.answer(PAYMENT_PROBLEM_TEXT)
        return

    if new_balance is None:
        # Повторная доставка апдейта (например, после рестарта) — уже начислено.
        return

    plural = (
        "генерация" if gens == 1
        else "генерации" if 2 <= gens <= 4
        else "генераций"
    )

    await message.answer(
        f"✅ Оплата прошла успешно!\n\n"
        f"Начислено: <b>{gens} {plural}</b>\n"
        f"Текущий баланс: <b>{new_balance}</b>",
        parse_mode="HTML",
    )