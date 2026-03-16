import asyncio
import logging
from io import BytesIO

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from openai import APIError, APITimeoutError

from bot.keyboards import main_keyboard
from bot.services.openai_client import (
    get_trump_reply, transcribe_voice, synthesize_speech,
    analyze_pronunciation,
)
from bot.services.vocab_extractor import extract_and_save_vocab
from bot.services.redis_client import redis_client
from bot.handlers.achievements import check_achievements, format_new_achievements

logger = logging.getLogger(__name__)

router = Router()

LIMIT_EXCEEDED_TEXT = (
    "You've used all your messages for today. "
    "Get Premium for unlimited access -- the best deal ever! "
    "Or come back tomorrow, we'll make English great again!"
)

API_ERROR_TEXT = (
    "Oops, something went wrong. Try again in a minute. "
    "Even the best have bad days, believe me!"
)


def _tts_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="\U0001f50a Listen", callback_data="tts")]
        ]
    )


async def _generate_and_cache_tts(message_id: int, text: str) -> None:
    try:
        audio = await synthesize_speech(text)
        await redis_client.save_tts_audio(message_id, audio)
    except Exception as exc:
        logger.error("TTS background error for msg %s: %s", message_id, exc)




@router.message(F.voice)
async def handle_voice_message(message: Message) -> None:
    user_id = message.from_user.id

    if await redis_client.is_limit_exceeded(user_id):
        await message.answer(LIMIT_EXCEEDED_TEXT, reply_markup=main_keyboard)
        return

    file = await message.bot.get_file(message.voice.file_id)
    bio = BytesIO()
    await message.bot.download_file(file.file_path, bio)
    audio_bytes = bio.getvalue()

    try:
        user_text = await transcribe_voice(audio_bytes)
    except (APIError, APITimeoutError) as exc:
        logger.error("STT error for user %s: %s", user_id, exc)
        await message.answer(API_ERROR_TEXT, reply_markup=main_keyboard)
        return

    if not user_text:
        await message.answer(
            "I couldn't understand your voice message. Try again, speak clearly!",
            reply_markup=main_keyboard,
        )
        return

    level = await redis_client.get_level(user_id)
    topic = await redis_client.get_topic(user_id)

    active_lesson = await redis_client.get_active_lesson(user_id)
    lesson_context = active_lesson if active_lesson else None

    expected_text = None
    if active_lesson and "target_vocabulary" in active_lesson:
        expected_text = ", ".join(active_lesson["target_vocabulary"])

    pronunciation_task = asyncio.create_task(
        analyze_pronunciation(user_text, expected_text)
    )

    await redis_client.append_message(user_id, "user", user_text)
    history = await redis_client.get_history(user_id)

    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        reply = await get_trump_reply(
            history, level=level, topic=topic, lesson_context=lesson_context
        )
    except (APIError, APITimeoutError) as exc:
        logger.error("OpenAI chat error for user %s: %s", user_id, exc)
        await redis_client.clear_history(user_id)
        for msg in history[:-1]:
            await redis_client.append_message(user_id, msg["role"], msg["content"])
        await message.answer(API_ERROR_TEXT, reply_markup=main_keyboard)
        pronunciation_task.cancel()
        return

    await redis_client.append_message(user_id, "assistant", reply)

    count = await redis_client.increment_requests(user_id)
    await redis_client.increment_total_messages(user_id)
    streak = await redis_client.update_streak(user_id)
    await redis_client.increment_voice_count(user_id)

    xp_amount = 5 + streak * 2 + 5
    if active_lesson:
        xp_amount += 5

    old_xp = await redis_client.get_xp(user_id)
    old_title = await redis_client.get_xp_level_title(old_xp)
    new_xp = await redis_client.add_xp(user_id, xp_amount)
    new_title = await redis_client.get_xp_level_title(new_xp)

    footer = ""

    try:
        pronunciation_tip = await pronunciation_task
        if pronunciation_tip:
            footer += f"\n\n🎤 Pronunciation tip: {pronunciation_tip}"
    except Exception as exc:
        logger.error("Pronunciation analysis error: %s", exc)

    if new_title != old_title:
        footer += f"\n\n🎉 LEVEL UP! You are now: {new_title}! Tremendous!"

    new_achievements = await check_achievements(user_id)
    footer += format_new_achievements(new_achievements)

    is_premium = await redis_client.is_premium(user_id)
    if not is_premium:
        effective_limit = await redis_client.get_effective_limit(user_id)
        remaining = effective_limit - count
        if 0 < remaining <= 5:
            footer += f"\n\n[{remaining} messages left today]"
        elif remaining <= 0:
            footer += "\n\n[This was your last message for today. Come back tomorrow!]"

    sent = await message.answer(
        reply + footer,
        reply_markup=_tts_keyboard(),
    )

    await redis_client.save_tts_text(sent.message_id, reply)
    asyncio.create_task(_generate_and_cache_tts(sent.message_id, reply))
    asyncio.create_task(extract_and_save_vocab(user_id, reply, level))


@router.callback_query(F.data == "tts")
async def handle_tts_callback(callback: CallbackQuery) -> None:
    message_id = callback.message.message_id

    audio = await redis_client.get_tts_audio(message_id)

    if not audio:
        text = await redis_client.get_tts_text(message_id)
        if not text:
            await callback.answer("Message expired. Send a new one!")
            return
        try:
            audio = await synthesize_speech(text)
            await redis_client.save_tts_audio(message_id, audio)
        except Exception as exc:
            logger.error("TTS retry error: %s", exc)
            await callback.answer("Try again!")
            return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.reply_voice(
        BufferedInputFile(audio, filename="reply.ogg"),
    )
    await callback.answer()
