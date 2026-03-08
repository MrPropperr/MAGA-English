from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎙 Начать урок / Поболтать")],
        [KeyboardButton(text="🔄 Сбросить контекст")],
        [KeyboardButton(text="ℹ️ Лимиты и подписка")],
    ],
    resize_keyboard=True,
    persistent=True,
)
