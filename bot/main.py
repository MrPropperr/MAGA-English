import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import BOT_TOKEN
from bot.handlers import (
    start, reset, level, topic, stats, daily,
    payment, referral, quiz, leaderboard, achievements,
    vocab, lessons,
    voice, chat,
)
from bot.services.redis_client import redis_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(reset.router)
    dp.include_router(level.router)
    dp.include_router(topic.router)
    dp.include_router(stats.router)
    dp.include_router(daily.router)
    dp.include_router(payment.router)
    dp.include_router(referral.router)
    dp.include_router(quiz.router)
    dp.include_router(leaderboard.router)
    dp.include_router(achievements.router)
    dp.include_router(vocab.router)
    dp.include_router(lessons.router)
    dp.include_router(voice.router)
    dp.include_router(chat.router)

    await redis_client.connect()
    logger.info("Redis connected")

    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await redis_client.close()
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
