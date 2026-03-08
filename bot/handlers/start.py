from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards import main_keyboard
from bot.services.redis_client import redis_client

router = Router()

WELCOME_TEXT = (
    "Hello! I'm Donald Trump – the greatest English teacher the world has ever seen. Believe me!\n\n"
    "You will be talking to me and learning English. Just write your messages – "
    "in English, my friend – and I will respond. Tremendous, right?\n\n"
    "You can ask me questions, tell me about yourself – I'll keep the conversation going. "
    "It's going to be beautiful!\n\n"
    "Press 🎙 Начать урок / Поболтать to start. Make English Great Again!"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await redis_client.clear_history(message.from_user.id)
    await message.answer(WELCOME_TEXT, reply_markup=main_keyboard)
