import asyncio
import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

import database as db
from config import is_admin, load_admin_users
from kie_ai import get_account_credits
from keyboards import MenuCallback, admin_panel_keyboard

logger = logging.getLogger(__name__)
router = Router()


def _fmt_credits(c) -> str | None:
    """Форматирует баланс KIE (приходит числом, иногда float) без хвоста .0."""
    if isinstance(c, bool) or not isinstance(c, (int, float)):
        return None
    return str(int(c)) if float(c).is_integer() else str(c)


async def build_admin_text() -> str:
    stats = await db.get_admin_stats()
    accounts = stats["accounts"]
    active = [a for a in accounts if a.is_active]

    # Опрашиваем баланс активных аккаунтов KIE параллельно.
    credits = await asyncio.gather(*[get_account_credits(a.token) for a in active]) if active else []
    credit_by_id = {a.id: c for a, c in zip(active, credits)}
    total_credits = sum(c for c in credits if isinstance(c, (int, float)) and not isinstance(c, bool))

    acc_lines = []
    for a in accounts:
        if a.is_active:
            bal = _fmt_credits(credit_by_id.get(a.id))
            acc_lines.append(f"  🟢 #{a.id} {a.email or '—'}: <b>{bal or 'n/a'}</b>")
        else:
            acc_lines.append(f"  🔴 #{a.id} {a.email or '—'}: <i>отключён</i>")
    acc_block = "\n".join(acc_lines) if acc_lines else "  <i>нет аккаунтов</i>"

    return (
        "🛠 <b>Панель управления</b>\n\n"
        f"👥 <b>Пользователи:</b> {stats['total_users']} "
        f"(+{stats['new_users_month']} за месяц)\n\n"
        f"🖼 <b>Генерации:</b> {stats['gens_total']} всего\n"
        f"   За месяц: {stats['gens_month']} "
        f"(✅ {stats['gens_success_month']} / ❌ {stats['gens_failed_month']})\n\n"
        f"🔑 <b>Аккаунты KIE.ai:</b> {len(active)}/{len(accounts)} активны\n"
        f"{acc_block}\n\n"
        f"💰 <b>Кредитов на активных:</b> {_fmt_credits(total_credits) or 0}"
    )


@router.callback_query(MenuCallback.filter(F.action == "admin"))
async def on_admin_panel(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        await query.answer("⛔️ Недостаточно прав.", show_alert=True)
        return
    await query.answer()
    text = await build_admin_text()
    try:
        await query.message.edit_text(text, reply_markup=admin_panel_keyboard(), parse_mode="HTML")
    except Exception:
        # «message is not modified» при повторном «Обновить» с теми же цифрами — игнорируем.
        pass


async def notify_admins(bot, text: str, exclude_tg_id: int | None = None) -> None:
    """Рассылает текст всем админам (кроме exclude_tg_id). Ошибки доставки молчаливы."""
    for admin_id in load_admin_users():
        if admin_id == exclude_tg_id:
            continue
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception as exc:
            logger.warning("Failed to notify admin %s: %s", admin_id, exc)
