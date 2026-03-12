import logging

from aiogram import Router, F
from aiogram.types import Message
from openai import APIError, APITimeoutError

from bot.config import DAILY_LIMIT
from bot.keyboards import main_keyboard
from bot.services.openai_client import get_trump_reply
from bot.services.redis_client import redis_client

logger = logging.getLogger(__name__)

router = Router()

LIMIT_EXCEEDED_TEXT = (
    "You've used all your messages for today. Come back tomorrow – "
    "we'll make English great again! Premium is coming soon."
)

API_ERROR_TEXT = (
    "Oops, something went wrong. Try again in a minute. "
    "Even the best have bad days, believe me!"
)

START_CHAT_TEXT = (
    "Let's go! Talk to me – I'm all ears. "
    "What do you want to discuss today? It's going to be fantastic!"
)

SUBSCRIPTION_STUB_TEXT = (
    "ℹ️ Subscription coming soon!\n\n"
    f"Free plan: {DAILY_LIMIT} messages per day.\n"
    "Premium plan will give you unlimited access and exclusive lesson scenarios. "
    "Stay tuned – it's going to be tremendous!"
)


@router.message(F.text == "🎙 Начать урок / Поболтать")
async def btn_start_chat(message: Message) -> None:
    await message.answer(START_CHAT_TEXT, reply_markup=main_keyboard)


@router.message(F.text == "ℹ️ Лимиты и подписка")
async def btn_subscription(message: Message) -> None:
    await message.answer(SUBSCRIPTION_STUB_TEXT, reply_markup=main_keyboard)


@router.message(F.text)
async def handle_chat_message(message: Message) -> None:
    user_id = message.from_user.id
    user_text = message.text.strip()

    if await redis_client.is_limit_exceeded(user_id):
        await message.answer(LIMIT_EXCEEDED_TEXT, reply_markup=main_keyboard)
        return

    await redis_client.append_message(user_id, "user", user_text)
    history = await redis_client.get_history(user_id)
    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        reply = await get_trump_reply(history)
    except (APIError, APITimeoutError) as exc:
        logger.error("OpenAI error for user %s: %s", user_id, exc)
        await redis_client.clear_history(user_id)
        for msg in history[:-1]:
            await redis_client.append_message(user_id, msg["role"], msg["content"])
        await message.answer(API_ERROR_TEXT, reply_markup=main_keyboard)
        return

    await redis_client.append_message(user_id, "assistant", reply)
    count = await redis_client.increment_requests(user_id)

    remaining = DAILY_LIMIT - count
    footer = ""
    if remaining <= 5 and remaining > 0:
        footer = f"\n\n[{remaining} messages left today]"
    elif remaining == 0:
        footer = "\n\n[This was your last message for today. Come back tomorrow!]"

    await message.answer(reply + footer, reply_markup=main_keyboard)
