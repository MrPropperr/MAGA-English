from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from bot.keyboards import main_keyboard
from bot.services.redis_client import redis_client

router = Router()

RANK_EMOJIS = ["🥇", "🥈", "🥉"]


@router.message(Command("top"))
@router.message(F.text == "🏆 Рейтинг")
async def cmd_leaderboard(message: Message) -> None:
    user_id = message.from_user.id
    top = await redis_client.get_leaderboard(10)

    if not top:
        await message.answer(
            "Nobody on the leaderboard yet. Be the first! It's wide open, like a new market!",
            reply_markup=main_keyboard,
        )
        return

    lines = ["🏆 Top Players -- The Best of the Best!\n"]

    for i, (member_id, score) in enumerate(top):
        username = await redis_client.get_username(int(member_id))
        display = f"@{username}" if username else f"Player {member_id}"
        emoji = RANK_EMOJIS[i] if i < 3 else f"#{i + 1}"
        title = await redis_client.get_xp_level_title(int(score))
        lines.append(f"{emoji} {display} -- {int(score)} XP ({title})")

    my_rank = await redis_client.get_leaderboard_rank(user_id)
    my_xp = await redis_client.get_xp(user_id)
    if my_rank:
        lines.append(f"\nYour rank: #{my_rank} with {my_xp} XP. Keep climbing!")
    else:
        lines.append("\nYou're not on the board yet. Send some messages and get those XP!")

    await message.answer("\n".join(lines), reply_markup=main_keyboard)
