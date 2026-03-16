from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from bot.keyboards import main_keyboard
from bot.services.redis_client import redis_client

router = Router()

LEVEL_LABELS = {
    "beginner": "🟢 Beginner",
    "intermediate": "🟡 Intermediate",
    "advanced": "🔴 Advanced",
}

TOPIC_LABELS = {
    "business": "💼 Business",
    "travel": "✈️ Travel",
    "food": "🍕 Food",
    "sports": "⚽ Sports",
    "movies": "🎬 Movies",
    "daily_life": "🏠 Daily Life",
    "job_interview": "👔 Job Interview",
}


@router.message(Command("stats"))
@router.message(F.text == "📊 Статистика")
async def cmd_stats(message: Message) -> None:
    user_id = message.from_user.id

    total = await redis_client.get_total_messages(user_id)
    streak = await redis_client.get_streak(user_id)
    level = await redis_client.get_level(user_id)
    topic = await redis_client.get_topic(user_id)
    title, xp, next_level_xp = await redis_client.get_xp_level(user_id)
    quiz_correct, quiz_total = await redis_client.get_quiz_stats(user_id)
    is_premium = await redis_client.is_premium(user_id)

    level_label = LEVEL_LABELS.get(level, level)
    topic_label = TOPIC_LABELS.get(topic, "Not set") if topic else "Not set"

    xp_progress = f"{xp}/{next_level_xp} XP" if next_level_xp > 0 else f"{xp} XP (MAX)"

    text = (
        "📊 Your Stats -- and they are fantastic, believe me!\n\n"
        f"🏅 Rank: {title}\n"
        f"⚡ XP: {xp_progress}\n"
        f"💬 Total messages: {total}\n"
        f"🔥 Current streak: {streak} day{'s' if streak != 1 else ''}\n"
        f"🧠 Quiz: {quiz_correct}/{quiz_total} correct\n"
        f"📚 Level: {level_label}\n"
        f"🎯 Topic: {topic_label}\n"
        f"⭐ Premium: {'Active' if is_premium else 'No'}\n\n"
        "Keep going! You're doing better than most people, I can tell you that."
    )
    await message.answer(text, reply_markup=main_keyboard)
