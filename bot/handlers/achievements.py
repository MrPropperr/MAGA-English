from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from bot.keyboards import main_keyboard
from bot.services.redis_client import redis_client

router = Router()

ACHIEVEMENT_DEFS = {
    "first_message": {
        "icon": "💬",
        "title": "First Words",
        "description": "Sent your first message. The beginning of something huge!",
    },
    "streak_7": {
        "icon": "🔥",
        "title": "Week Warrior",
        "description": "7-day streak. That's what I call commitment!",
    },
    "streak_30": {
        "icon": "🏆",
        "title": "Monthly Champion",
        "description": "30-day streak. You're more dedicated than most of my cabinet!",
    },
    "quiz_master": {
        "icon": "🧠",
        "title": "Quiz Master",
        "description": "10 correct quiz answers. Very stable genius!",
    },
    "voice_10": {
        "icon": "🎙",
        "title": "Voice of the People",
        "description": "10 voice messages. Beautiful voice, believe me!",
    },
    "xp_100": {
        "icon": "⭐",
        "title": "Rising Star",
        "description": "100 XP earned. You're going places, my friend!",
    },
    "xp_500": {
        "icon": "🌟",
        "title": "Superstar",
        "description": "500 XP earned. Tremendous talent!",
    },
    "xp_1000": {
        "icon": "👑",
        "title": "The Best",
        "description": "1000 XP earned. You're at the top. The very top!",
    },
    "daily_learner": {
        "icon": "📚",
        "title": "Daily Learner",
        "description": "Used word of the day 5 times. You love learning, I can tell!",
    },
}


async def check_achievements(user_id: int) -> list[str]:
    earned = []

    total = await redis_client.get_total_messages(user_id)
    if total >= 1:
        if await redis_client.grant_achievement(user_id, "first_message"):
            earned.append("first_message")

    streak = await redis_client.get_streak(user_id)
    if streak >= 7:
        if await redis_client.grant_achievement(user_id, "streak_7"):
            earned.append("streak_7")
    if streak >= 30:
        if await redis_client.grant_achievement(user_id, "streak_30"):
            earned.append("streak_30")

    quiz_correct, _ = await redis_client.get_quiz_stats(user_id)
    if quiz_correct >= 10:
        if await redis_client.grant_achievement(user_id, "quiz_master"):
            earned.append("quiz_master")

    voice_count = await redis_client.get_voice_count(user_id)
    if voice_count >= 10:
        if await redis_client.grant_achievement(user_id, "voice_10"):
            earned.append("voice_10")

    xp = await redis_client.get_xp(user_id)
    if xp >= 100:
        if await redis_client.grant_achievement(user_id, "xp_100"):
            earned.append("xp_100")
    if xp >= 500:
        if await redis_client.grant_achievement(user_id, "xp_500"):
            earned.append("xp_500")
    if xp >= 1000:
        if await redis_client.grant_achievement(user_id, "xp_1000"):
            earned.append("xp_1000")

    daily_word_count = await redis_client.get_daily_word_count(user_id)
    if daily_word_count >= 5:
        if await redis_client.grant_achievement(user_id, "daily_learner"):
            earned.append("daily_learner")

    return earned


def format_new_achievements(earned: list[str]) -> str:
    if not earned:
        return ""
    lines = []
    for key in earned:
        a = ACHIEVEMENT_DEFS[key]
        lines.append(f"\n\n🏅 Achievement Unlocked: {a['icon']} {a['title']}! {a['description']}")
    return "".join(lines)


@router.message(Command("achievements"))
@router.message(F.text == "🎖 Достижения")
async def cmd_achievements(message: Message) -> None:
    user_id = message.from_user.id
    user_achievements = await redis_client.get_achievements(user_id)

    lines = ["🎖 Your Achievements -- and they are spectacular, believe me!\n"]

    for key, a in ACHIEVEMENT_DEFS.items():
        if key in user_achievements:
            lines.append(f"✅ {a['icon']} {a['title']} -- {a['description']}")
        else:
            lines.append(f"🔒 {a['icon']} {a['title']} -- ???")

    earned_count = len(user_achievements)
    total_count = len(ACHIEVEMENT_DEFS)
    lines.append(f"\n{earned_count}/{total_count} unlocked. Keep going, you're doing fantastic!")

    await message.answer("\n".join(lines), reply_markup=main_keyboard)
