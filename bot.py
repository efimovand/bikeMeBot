import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage
from config import settings
from handlers import bike, helmet, jacket, suit, glove, boot, photos, start, generate, location, payment

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main():
    session = AiohttpSession(proxy=settings.proxy_tg_url)
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
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())