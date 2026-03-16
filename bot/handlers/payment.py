import logging

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    PreCheckoutQuery,
    Message,
    LabeledPrice,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from bot.keyboards import main_keyboard
from bot.services.redis_client import redis_client

logger = logging.getLogger(__name__)

router = Router()

PREMIUM_OPTIONS = [
    {"label": "1 Day -- 25 ⭐", "days": 1, "stars": 25, "callback": "buy_premium:1"},
    {"label": "7 Days -- 100 ⭐", "days": 7, "stars": 100, "callback": "buy_premium:7"},
    {"label": "30 Days -- 300 ⭐", "days": 30, "stars": 300, "callback": "buy_premium:30"},
]


def _premium_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=opt["label"], callback_data=opt["callback"])]
        for opt in PREMIUM_OPTIONS
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(lambda c: c.data and c.data.startswith("buy_premium:"))
async def handle_buy_premium(callback: CallbackQuery) -> None:
    days = int(callback.data.split(":")[1])
    option = next(opt for opt in PREMIUM_OPTIONS if opt["days"] == days)

    await callback.message.bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"Premium -- {option['days']} Day{'s' if option['days'] > 1 else ''}",
        description=(
            "Unlimited messages, no daily limits. "
            "The best deal you'll ever make, believe me!"
        ),
        payload=f"premium_{days}",
        currency="XTR",
        prices=[LabeledPrice(label="Premium", amount=option["stars"])],
        provider_token="",
    )
    await callback.answer()


@router.pre_checkout_query()
async def handle_pre_checkout(pre_checkout_query: PreCheckoutQuery) -> None:
    payload = pre_checkout_query.invoice_payload
    valid_payloads = {f"premium_{opt['days']}" for opt in PREMIUM_OPTIONS}
    if payload not in valid_payloads:
        await pre_checkout_query.answer(ok=False, error_message="Invalid payment option.")
        return
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def handle_successful_payment(message: Message) -> None:
    user_id = message.from_user.id
    payload = message.successful_payment.invoice_payload
    days = int(payload.split("_")[1])

    await redis_client.activate_premium(user_id, days)

    await message.answer(
        f"Fantastic! You just got {days} day{'s' if days > 1 else ''} of Premium access. "
        "Unlimited messages, no limits, the best deal in the history of deals. "
        "Now let's get back to making your English great again!",
        reply_markup=main_keyboard,
    )
