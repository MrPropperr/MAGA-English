from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.keyboards import main_keyboard
from bot.services.redis_client import redis_client

router = Router()


async def process_referral(user_id: int, referrer_id: int) -> None:
    if user_id == referrer_id:
        return
    existing = await redis_client.get_referred_by(user_id)
    if existing:
        return
    await redis_client.set_referred_by(user_id, referrer_id)
    await redis_client.increment_referrals(referrer_id)
    await redis_client.add_bonus_messages(referrer_id, 10)


@router.message(Command("referral"))
@router.message(Command("ref"))
async def cmd_referral(message: Message) -> None:
    user_id = message.from_user.id
    bot_info = await message.bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    referrals = await redis_client.get_referrals(user_id)
    bonus = await redis_client.get_bonus_messages(user_id)

    text = (
        "📣 Your Referral Link -- share it, spread the word!\n\n"
        f"{referral_link}\n\n"
        f"👥 Friends referred: {referrals}\n"
        f"🎁 Bonus messages earned: {bonus}\n\n"
        "Every friend who joins gives you 10 extra messages. "
        "It's the art of the deal, my friend!"
    )
    await message.answer(text, reply_markup=main_keyboard)
