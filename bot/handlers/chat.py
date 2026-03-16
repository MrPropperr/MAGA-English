import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from openai import APIError, APITimeoutError

from bot.config import DAILY_LIMIT
from bot.keyboards import main_keyboard
from bot.services.openai_client import get_trump_reply
from bot.services.redis_client import redis_client
from bot.services.vocab_extractor import extract_and_save_vocab
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

START_CHAT_TEXT = (
    "Let's go! Talk to me -- I'm all ears. "
    "What do you want to discuss today? It's going to be fantastic!"
)


def _premium_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="1 Day -- 25 ⭐", callback_data="buy_premium:1")],
            [InlineKeyboardButton(text="7 Days -- 100 ⭐", callback_data="buy_premium:7")],
            [InlineKeyboardButton(text="30 Days -- 300 ⭐", callback_data="buy_premium:30")],
        ]
    )



@router.message(F.text == "🎙 Начать урок / Поболтать")
async def btn_start_chat(message: Message) -> None:
    await message.answer(START_CHAT_TEXT, reply_markup=main_keyboard)


@router.message(F.text == "ℹ️ Лимиты и подписка")
async def btn_subscription(message: Message) -> None:
    user_id = message.from_user.id
    is_premium = await redis_client.is_premium(user_id)

    if is_premium:
        premium_until = await redis_client.get_premium_until(user_id)
        if premium_until:
            dt = datetime.fromtimestamp(premium_until, tz=timezone.utc)
            date_str = dt.strftime("%Y-%m-%d %H:%M UTC")
            text = (
                "⭐ You have PREMIUM access -- unlimited messages!\n"
                f"Active until: {date_str}\n\n"
                "You made the best deal. Extend it if you want even more!"
            )
        else:
            text = "⭐ You have PREMIUM access -- unlimited messages!"
    else:
        requests_today = await redis_client.get_requests_today(user_id)
        effective_limit = await redis_client.get_effective_limit(user_id)
        remaining = max(0, effective_limit - requests_today)
        text = (
            f"Free plan: {DAILY_LIMIT} messages per day.\n"
            f"Messages left today: {remaining}\n\n"
            "Want unlimited access? Get Premium -- it's the best deal, believe me!"
        )

    await message.answer(text, reply_markup=_premium_keyboard())


@router.message(F.text)
async def handle_chat_message(message: Message) -> None:
    user_id = message.from_user.id
    user_text = message.text.strip()

    if await redis_client.is_limit_exceeded(user_id):
        await message.answer(LIMIT_EXCEEDED_TEXT, reply_markup=_premium_keyboard())
        return

    level = await redis_client.get_level(user_id)
    topic = await redis_client.get_topic(user_id)

    active_lesson = await redis_client.get_active_lesson(user_id)
    lesson_context = active_lesson if active_lesson else None

    await redis_client.append_message(user_id, "user", user_text)
    history = await redis_client.get_history(user_id)
    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        reply = await get_trump_reply(
            history, level=level, topic=topic, lesson_context=lesson_context
        )
    except (APIError, APITimeoutError) as exc:
        logger.error("OpenAI error for user %s: %s", user_id, exc)
        await redis_client.clear_history(user_id)
        for msg in history[:-1]:
            await redis_client.append_message(user_id, msg["role"], msg["content"])
        await message.answer(API_ERROR_TEXT, reply_markup=main_keyboard)
        return

    await redis_client.append_message(user_id, "assistant", reply)
    count = await redis_client.increment_requests(user_id)
    await redis_client.increment_total_messages(user_id)
    streak = await redis_client.update_streak(user_id)

    xp_amount = 5 + streak * 2
    if active_lesson:
        xp_amount += 5

    old_xp = await redis_client.get_xp(user_id)
    old_title = await redis_client.get_xp_level_title(old_xp)
    new_xp = await redis_client.add_xp(user_id, xp_amount)
    new_title = await redis_client.get_xp_level_title(new_xp)

    footer = ""

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

    await message.answer(reply + footer, reply_markup=main_keyboard)

    asyncio.create_task(extract_and_save_vocab(user_id, reply, level))
