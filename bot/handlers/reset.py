from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from bot.keyboards import main_keyboard
from bot.services.redis_client import redis_client

router = Router()

RESET_TEXT = (
    "New conversation, new opportunities. Tremendous! "
    "Write your first message, my friend."
)


@router.message(Command("reset"))
@router.message(F.text == "🔄 Сбросить контекст")
async def cmd_reset(message: Message) -> None:
    await redis_client.clear_history(message.from_user.id)
    await message.answer(RESET_TEXT, reply_markup=main_keyboard)
