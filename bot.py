import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import ClientTimeout
from aiogram.fsm.storage.memory import MemoryStorage
from config import settings
from handlers import bike, helmet, jacket, suit, glove, boot, photos, start, generate, location, payment

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


async def main():
    # Cleanup осиротевших pending генераций (если бот падал во время генерации).
    import database as db
    reset_count = await db.reset_pending_generations()
    if reset_count:
        logging.info("Reset %d pending generation(s) to failed on startup", reset_count)

    session = AiohttpSession(proxy=settings.proxy_tg_url, timeout=ClientTimeout(total=120))
    bot = Bot(token=settings.bot_token, session=session)

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start.router)
    dp.include_router(bike.router)
    dp.include_router(location.router)
    dp.include_router(helmet.router)
    dp.include_router(jacket.router)
    dp.include_router(suit.router)
    dp.include_router(glove.router)
    dp.include_router(boot.router)
    dp.include_router(photos.router)
    dp.include_router(generate.router)
    dp.include_router(payment.router)

    logging.info("Bot started")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        # Закрываем переиспользуемый HTTP-клиент для kie.ai.
        from kie_ai import close_http_session
        await close_http_session()


if __name__ == "__main__":
    asyncio.run(main())