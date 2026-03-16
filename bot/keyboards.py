from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎙 Начать урок / Поболтать")],
        [
            KeyboardButton(text="🧠 Квиз"),
            KeyboardButton(text="📝 Слово дня"),
        ],
        [
            KeyboardButton(text="🎯 Сменить тему"),
            KeyboardButton(text="📊 Статистика"),
        ],
        [
            KeyboardButton(text="🏆 Рейтинг"),
            KeyboardButton(text="🎖 Достижения"),
        ],
        [
            KeyboardButton(text="📚 Словарь"),
            KeyboardButton(text="📖 Уроки"),
        ],
        [
            KeyboardButton(text="🔄 Сбросить контекст"),
            KeyboardButton(text="ℹ️ Лимиты и подписка"),
        ],
    ],
    resize_keyboard=True,
    persistent=True,
)
