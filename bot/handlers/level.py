from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.services.redis_client import redis_client

router = Router()

LEVEL_LABELS = {
    "beginner": "🟢 Beginner",
    "intermediate": "🟡 Intermediate",
    "advanced": "🔴 Advanced",
}


def _level_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Beginner", callback_data="level:beginner")],
            [InlineKeyboardButton(text="🟡 Intermediate", callback_data="level:intermediate")],
            [InlineKeyboardButton(text="🔴 Advanced", callback_data="level:advanced")],
        ]
    )


@router.message(Command("level"))
async def cmd_level(message: Message) -> None:
    current = await redis_client.get_level(message.from_user.id)
    await message.answer(
        f"Your current level: {LEVEL_LABELS.get(current, current)}\n\n"
        "Pick your level, my friend. Be honest -- I'll know if you're lying!",
        reply_markup=_level_keyboard(),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("level:"))
async def handle_level_callback(callback: CallbackQuery) -> None:
    level = callback.data.split(":")[1]
    await redis_client.set_level(callback.from_user.id, level)
    label = LEVEL_LABELS.get(level, level)
    await callback.message.edit_text(
        f"Level set to {label}. Fantastic choice! "
        "Now let's get back to making your English great again!",
    )
    await callback.answer()
