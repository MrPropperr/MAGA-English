from aiogram import Router
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message

from bot.keyboards import main_keyboard
from bot.services.redis_client import redis_client
from bot.handlers.referral import process_referral

router = Router()

WELCOME_TEXT = (
    "Hello! I'm Donald Trump -- the greatest English teacher the world has ever seen. Believe me!\n\n"
    "You will be talking to me and learning English. Just write your messages -- "
    "in English, my friend -- and I will respond. Tremendous, right?\n\n"
    "You can ask me questions, tell me about yourself -- I'll keep the conversation going. "
    "It's going to be beautiful!\n\n"
    "Press 🎙 Начать урок / Поболтать to start. Make English Great Again!"
)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject) -> None:
    user_id = message.from_user.id
    username = message.from_user.username
    if username:
        await redis_client.save_username(user_id, username)

    if command.args and command.args.startswith("ref_"):
        try:
            referrer_id = int(command.args[4:])
            await process_referral(user_id, referrer_id)
        except ValueError:
            pass

    await redis_client.clear_history(user_id)
    streak = await redis_client.get_streak(user_id)
    streak_text = ""
    if streak > 0:
        streak_text = f"\n\n🔥 Your streak: {streak} day{'s' if streak != 1 else ''}!"
    await message.answer(WELCOME_TEXT + streak_text, reply_markup=main_keyboard)
