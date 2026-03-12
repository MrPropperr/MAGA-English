import logging
from io import BytesIO

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from openai import APIError, APITimeoutError

from bot.config import DAILY_LIMIT
from bot.keyboards import main_keyboard
from bot.services.openai_client import get_trump_reply, transcribe_voice, synthesize_speech
from bot.services.redis_client import redis_client

logger = logging.getLogger(__name__)

router = Router()

LIMIT_EXCEEDED_TEXT = (
    "Вы исчерпали дневной лимит сообщений. Возвращайтесь завтра!\n\n"
    "You've used all your messages for today. Come back tomorrow – "
    "we'll make English great again! А пока можете подписаться на платный тариф (скоро)."
)

API_ERROR_TEXT = (
    "Извините, технические неполадки. Попробуйте через минуту. "
    "Даже у лучших иногда бывают сбои!"
)


def _tts_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="\U0001f50a Озвучить", callback_data="tts")]
        ]
    )


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
            "Не удалось распознать речь. Попробуйте ещё раз.",
            reply_markup=main_keyboard,
        )
        return

    await redis_client.append_message(user_id, "user", user_text)
    history = await redis_client.get_history(user_id)

    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        reply = await get_trump_reply(history)
    except (APIError, APITimeoutError) as exc:
        logger.error("OpenAI chat error for user %s: %s", user_id, exc)
        await redis_client.clear_history(user_id)
        for msg in history[:-1]:
            await redis_client.append_message(user_id, msg["role"], msg["content"])
        await message.answer(API_ERROR_TEXT, reply_markup=main_keyboard)
        return

    await redis_client.append_message(user_id, "assistant", reply)

    count = await redis_client.increment_requests(user_id)
    remaining = DAILY_LIMIT - count
    footer = ""
    if 0 < remaining <= 5:
        footer = f"\n\n[{remaining} messages left today]"
    elif remaining == 0:
        footer = "\n\n[This was your last message for today. Come back tomorrow!]"

    sent = await message.answer(
        reply + footer,
        reply_markup=_tts_keyboard(),
    )

    await redis_client.save_tts_text(sent.message_id, reply)

    try:
        audio = await synthesize_speech(reply)
    except Exception as exc:
        logger.error("TTS error for user %s: %s", user_id, exc)
        return

    await message.answer_voice(
        BufferedInputFile(audio, filename="reply.ogg"),
    )
    try:
        await sent.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@router.callback_query(F.data == "tts")
async def handle_tts_callback(callback: CallbackQuery) -> None:
    message_id = callback.message.message_id
    text = await redis_client.get_tts_text(message_id)

    if not text:
        await callback.answer("Текст устарел, отправьте сообщение заново.")
        return

    try:
        audio = await synthesize_speech(text)
    except Exception as exc:
        logger.error("TTS retry error: %s", exc)
        await callback.answer("Попробуйте ещё раз")
        return

    await callback.message.answer_voice(
        BufferedInputFile(audio, filename="reply.ogg"),
    )
    await callback.answer("Готово!")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
