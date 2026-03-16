import logging
from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from openai import APIError, APITimeoutError

from bot.keyboards import main_keyboard
from bot.services.openai_client import generate_daily_word
from bot.services.redis_client import redis_client
from bot.handlers.achievements import check_achievements, format_new_achievements

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("word"))
@router.message(F.text == "📝 Слово дня")
async def cmd_daily_word(message: Message) -> None:
    user_id = message.from_user.id
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    level = await redis_client.get_level(user_id)

    cache_key = f"{today}:{level}"
    word_data = await redis_client.get_daily_word(cache_key)

    if not word_data:
        await message.bot.send_chat_action(message.chat.id, "typing")
        try:
            word_data = await generate_daily_word(level=level)
            await redis_client.save_daily_word(cache_key, word_data)
        except (APIError, APITimeoutError) as exc:
            logger.error("Failed to generate daily word: %s", exc)
            await message.answer(
                "Couldn't get today's word right now. Even I have technical difficulties sometimes. Try again!",
                reply_markup=main_keyboard,
            )
            return

    word = word_data.get("word", "N/A")
    definition = word_data.get("definition", "N/A")
    example = word_data.get("example", "N/A")
    task = word_data.get("task", "N/A")

    await redis_client.increment_daily_word_count(user_id)

    daily_xp_key = f"trump_bot:user:{user_id}:daily_word_xp:{today}"
    already_claimed = await redis_client.r.exists(daily_xp_key)

    footer = ""
    if not already_claimed:
        await redis_client.r.set(daily_xp_key, "1", ex=86400)
        old_xp = await redis_client.get_xp(user_id)
        old_title = await redis_client.get_xp_level_title(old_xp)
        new_xp = await redis_client.add_xp(user_id, 10)
        new_title = await redis_client.get_xp_level_title(new_xp)
        footer = "\n+10 XP for checking the word of the day!"
        if new_title != old_title:
            footer += f"\n\n🎉 LEVEL UP! You are now: {new_title}! Tremendous!"

    new_achievements = await check_achievements(user_id)
    footer += format_new_achievements(new_achievements)

    text = (
        f"📝 Word of the Day -- {today}\n\n"
        f"🔤 Word: {word}\n\n"
        f"📖 Definition: {definition}\n\n"
        f"💬 Example: {example}\n\n"
        f"🎯 Your challenge: {task}\n\n"
        "Go ahead, use it in a sentence! Send me your best shot, my friend!"
        f"{footer}"
    )
    await message.answer(text, reply_markup=main_keyboard)
