import json
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.keyboards import main_keyboard
from bot.services.redis_client import redis_client
from bot.handlers.achievements import check_achievements, format_new_achievements

logger = logging.getLogger(__name__)

router = Router()


def _vocab_review_keyboard(word_json: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Show Definition", callback_data=f"vocab_show:{word_json}")],
        ]
    )


def _vocab_result_keyboard(word_json: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Knew it", callback_data=f"vocab_ok:{word_json}"),
                InlineKeyboardButton(text="❌ Forgot", callback_data=f"vocab_fail:{word_json}"),
            ],
        ]
    )


@router.message(Command("vocab"))
@router.message(F.text == "📚 Словарь")
async def cmd_vocab(message: Message) -> None:
    user_id = message.from_user.id
    due_words = await redis_client.get_due_words(user_id, limit=1)

    if due_words:
        word_data = due_words[0]
        word_json = json.dumps(word_data, ensure_ascii=False)
        if len(word_json) > 60:
            word_json_short = json.dumps({"word": word_data["word"], "definition": word_data["definition"][:40], "interval": word_data.get("interval", 1)}, ensure_ascii=False)
        else:
            word_json_short = word_json

        await redis_client.r.set(
            f"trump_bot:vocab_review:{user_id}",
            json.dumps(word_data, ensure_ascii=False),
            ex=3600,
        )

        text = (
            f"📚 Flashcard Time!\n\n"
            f"Word: <b>{word_data['word']}</b>\n\n"
            "Do you remember what it means? Think about it, then tap the button below!"
        )
        await message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Show Definition", callback_data="vocab_show")],
                ]
            ),
        )
    else:
        total = await redis_client.get_vocab_count(user_id)
        due_count = await redis_client.get_vocab_due_count(user_id)
        text = (
            "📚 Your Vocabulary -- and it's getting tremendous!\n\n"
            f"Total words learned: {total}\n"
            f"Words due for review: {due_count}\n\n"
        )
        if total == 0:
            text += "No words yet! Chat with me and I'll pick out the best words for you to learn. The best!"
        else:
            text += "No words due right now. Keep chatting and new words will come up for review. Believe me!"
        await message.answer(text, reply_markup=main_keyboard)


@router.callback_query(F.data == "vocab_show")
async def handle_vocab_show(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    raw = await redis_client.r.get(f"trump_bot:vocab_review:{user_id}")
    if not raw:
        await callback.answer("This card has expired. Try /vocab again!")
        return

    word_data = json.loads(raw)
    text = (
        f"📚 Flashcard\n\n"
        f"Word: <b>{word_data['word']}</b>\n"
        f"Definition: {word_data['definition']}\n\n"
        "Did you know it?"
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Knew it", callback_data="vocab_ok"),
                        InlineKeyboardButton(text="❌ Forgot", callback_data="vocab_fail"),
                    ],
                ]
            ),
        )
    except Exception:
        await callback.message.answer(text, reply_markup=main_keyboard)

    await callback.answer()


@router.callback_query(F.data.in_({"vocab_ok", "vocab_fail"}))
async def handle_vocab_result(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    correct = callback.data == "vocab_ok"

    raw = await redis_client.r.get(f"trump_bot:vocab_review:{user_id}")
    if not raw:
        await callback.answer("This card has expired. Try /vocab again!")
        return

    word_data = json.loads(raw)
    await redis_client.update_word_interval(user_id, word_data, correct)
    await redis_client.r.delete(f"trump_bot:vocab_review:{user_id}")

    old_xp = await redis_client.get_xp(user_id)
    old_title = await redis_client.get_xp_level_title(old_xp)
    new_xp = await redis_client.add_xp(user_id, 5)
    new_title = await redis_client.get_xp_level_title(new_xp)

    if correct:
        result_text = (
            f"✅ Tremendous! You remembered <b>{word_data['word']}</b>!\n"
            f"Next review in {word_data.get('interval', 2)} days. +5 XP!"
        )
    else:
        result_text = (
            f"❌ No worries! The word was <b>{word_data['word']}</b>.\n"
            f"Definition: {word_data['definition']}\n"
            "We'll review it again tomorrow. +5 XP for trying!"
        )

    footer = ""
    if new_title != old_title:
        footer += f"\n\n🎉 LEVEL UP! You are now: {new_title}! Tremendous!"

    new_achievements = await check_achievements(user_id)
    footer += format_new_achievements(new_achievements)

    due_remaining = await redis_client.get_vocab_due_count(user_id)
    if due_remaining > 0:
        footer += f"\n\n{due_remaining} more word{'s' if due_remaining != 1 else ''} to review. Use /vocab to continue!"

    try:
        await callback.message.edit_text(result_text + footer)
    except Exception:
        await callback.message.answer(result_text + footer, reply_markup=main_keyboard)

    await callback.answer()
