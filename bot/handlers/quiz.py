import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from openai import APIError, APITimeoutError

from bot.keyboards import main_keyboard
from bot.services.openai_client import generate_quiz
from bot.services.redis_client import redis_client
from bot.handlers.achievements import check_achievements, format_new_achievements

logger = logging.getLogger(__name__)

router = Router()

QUIZ_LABELS = {"A": "🅰️", "B": "🅱️", "C": "©️", "D": "🅳"}


def _quiz_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="A", callback_data="quiz_a"),
                InlineKeyboardButton(text="B", callback_data="quiz_b"),
            ],
            [
                InlineKeyboardButton(text="C", callback_data="quiz_c"),
                InlineKeyboardButton(text="D", callback_data="quiz_d"),
            ],
        ]
    )


@router.message(Command("quiz"))
@router.message(F.text == "🧠 Квиз")
async def cmd_quiz(message: Message) -> None:
    user_id = message.from_user.id
    level = await redis_client.get_level(user_id)

    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        quiz_data = await generate_quiz(level=level)
    except (APIError, APITimeoutError) as exc:
        logger.error("Quiz generation error for user %s: %s", user_id, exc)
        await message.answer(
            "Couldn't generate a quiz right now. Even I have off days sometimes. Try again!",
            reply_markup=main_keyboard,
        )
        return

    question = quiz_data.get("question", "What is the best word?")
    options = quiz_data.get("options", {"A": "?", "B": "?", "C": "?", "D": "?"})
    correct = quiz_data.get("correct", "A")
    explanation = quiz_data.get("explanation", "Because I said so!")

    text = (
        f"🧠 Quiz Time!\n\n"
        f"{question}\n\n"
        f"A) {options.get('A', '?')}\n"
        f"B) {options.get('B', '?')}\n"
        f"C) {options.get('C', '?')}\n"
        f"D) {options.get('D', '?')}"
    )

    sent = await message.answer(text, reply_markup=_quiz_keyboard())

    answer_data = f"{correct}|{explanation}"
    await redis_client.save_quiz_answer(user_id, sent.message_id, answer_data)


@router.callback_query(lambda c: c.data and c.data.startswith("quiz_"))
async def handle_quiz_answer(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    message_id = callback.message.message_id
    chosen = callback.data.split("_")[1].upper()

    stored = await redis_client.get_quiz_answer(user_id, message_id)
    if not stored:
        await callback.answer("This quiz has expired. Start a new one!")
        return

    correct, explanation = stored.split("|", 1)

    await redis_client.increment_quiz_total(user_id)

    if chosen == correct:
        await redis_client.increment_quiz_correct(user_id)
        xp_gained = 20
        result_text = (
            f"✅ Correct! The answer is {correct}. Tremendous!\n\n"
            f"{explanation}\n\n"
            f"+{xp_gained} XP. You're a winner!"
        )
    else:
        xp_gained = 5
        result_text = (
            f"❌ Wrong! You picked {chosen}, but the answer is {correct}. Sad!\n\n"
            f"{explanation}\n\n"
            f"+{xp_gained} XP. At least you tried, my friend."
        )

    old_xp = await redis_client.get_xp(user_id)
    old_title = await redis_client.get_xp_level_title(old_xp)
    new_xp = await redis_client.add_xp(user_id, xp_gained)
    new_title = await redis_client.get_xp_level_title(new_xp)

    if new_title != old_title:
        result_text += f"\n\n🎉 LEVEL UP! You are now: {new_title}! Fantastic!"

    new_achievements = await check_achievements(user_id)
    result_text += format_new_achievements(new_achievements)

    try:
        await callback.message.edit_text(
            callback.message.text + f"\n\n{result_text}",
        )
    except Exception:
        await callback.message.answer(result_text, reply_markup=main_keyboard)

    await callback.answer()
