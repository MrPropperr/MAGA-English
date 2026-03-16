from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.services.redis_client import redis_client

router = Router()

TOPIC_LABELS = {
    "business": "💼 Business",
    "travel": "✈️ Travel",
    "food": "🍕 Food",
    "sports": "⚽ Sports",
    "movies": "🎬 Movies",
    "daily_life": "🏠 Daily Life",
    "job_interview": "👔 Job Interview",
}


def _topic_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"topic:{key}")]
        for key, label in TOPIC_LABELS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("topic"))
@router.message(F.text == "🎯 Сменить тему")
async def cmd_topic(message: Message) -> None:
    current = await redis_client.get_topic(message.from_user.id)
    current_label = TOPIC_LABELS.get(current, "Not set") if current else "Not set"
    await message.answer(
        f"Current topic: {current_label}\n\n"
        "Pick a topic! I'm an expert in all of them, believe me. "
        "Nobody knows more about these topics than me!",
        reply_markup=_topic_keyboard(),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("topic:"))
async def handle_topic_callback(callback: CallbackQuery) -> None:
    topic = callback.data.split(":")[1]
    await redis_client.set_topic(callback.from_user.id, topic)
    label = TOPIC_LABELS.get(topic, topic)
    await callback.message.edit_text(
        f"Topic set to {label}. Tremendous choice! "
        "I know everything about this, probably more than anyone in history. Let's talk!",
    )
    await callback.answer()
