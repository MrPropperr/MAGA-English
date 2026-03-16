import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.keyboards import main_keyboard
from bot.services.redis_client import redis_client
from bot.handlers.achievements import check_achievements, format_new_achievements

logger = logging.getLogger(__name__)

router = Router()

LESSONS = {
    "job_interview": {
        "title": "Job Interview at Trump Tower",
        "description": "Practice your interview skills at the most tremendous building in Manhattan.",
        "system_prompt_modifier": (
            "You are now conducting a job interview at Trump Tower. "
            "You are the interviewer -- Donald Trump himself. "
            "Ask the student typical interview questions one at a time. "
            "Evaluate their answers, give feedback on their English, and coach them on how to impress. "
            "Start by welcoming them to Trump Tower and asking them to introduce themselves."
        ),
        "target_vocabulary": [
            "qualifications", "experience", "strengths", "weaknesses",
            "salary", "responsibilities", "resume", "references",
        ],
        "lesson_goal": "Complete a full mock job interview with at least 5 question-answer exchanges.",
    },
    "restaurant": {
        "title": "Ordering Food at Mar-a-Lago",
        "description": "Learn restaurant vocabulary at the classiest club in Florida.",
        "system_prompt_modifier": (
            "You are now a waiter at Mar-a-Lago, the finest restaurant. "
            "Guide the student through ordering a meal: greeting, seating, menu, ordering, "
            "asking about dishes, special requests, and paying the bill. "
            "Start by welcoming them to Mar-a-Lago and offering them a table."
        ),
        "target_vocabulary": [
            "appetizer", "entree", "dessert", "reservation",
            "check", "tip", "medium-rare", "specials",
        ],
        "lesson_goal": "Successfully order a complete meal from appetizer to dessert.",
    },
    "negotiation": {
        "title": "Negotiating The Best Deal",
        "description": "Master the art of the deal with business negotiation English.",
        "system_prompt_modifier": (
            "You are now in a business negotiation scenario. "
            "The student is trying to negotiate a deal with you -- Donald Trump. "
            "They are selling a product or service and must convince you to buy. "
            "Be a tough but fair negotiator. Teach them negotiation phrases and tactics. "
            "Start by setting the scene and asking what they're selling."
        ),
        "target_vocabulary": [
            "negotiate", "proposal", "counteroffer", "compromise",
            "terms", "agreement", "leverage", "bottom line",
        ],
        "lesson_goal": "Reach a deal agreement using proper negotiation vocabulary.",
    },
    "airport": {
        "title": "Airport & Travel",
        "description": "Navigate airports and travel situations like a world-class traveler.",
        "system_prompt_modifier": (
            "You are now at an international airport. "
            "Guide the student through travel scenarios: check-in, security, boarding, "
            "customs, asking for directions, dealing with delays. "
            "Play different characters (check-in agent, security officer, flight attendant). "
            "Start at the check-in counter."
        ),
        "target_vocabulary": [
            "boarding pass", "customs", "departure", "arrival",
            "layover", "turbulence", "carry-on", "declaration",
        ],
        "lesson_goal": "Navigate through all airport stages from check-in to arrival.",
    },
    "party": {
        "title": "Making Friends at a Party",
        "description": "Practice social English and small talk at a fabulous event.",
        "system_prompt_modifier": (
            "You are at a fancy party and the student just arrived. "
            "Practice small talk, introductions, and social conversation. "
            "Teach them how to start conversations, ask about interests, "
            "give compliments, and exchange contact information. "
            "Start by introducing yourself at the party."
        ),
        "target_vocabulary": [
            "pleasure", "occupation", "hobbies", "fascinating",
            "acquaintance", "mingle", "catch up", "get-together",
        ],
        "lesson_goal": "Successfully make small talk and exchange information with 3 party guests.",
    },
    "phone_call": {
        "title": "Phone Call with the President",
        "description": "Practice formal phone communication at the highest level.",
        "system_prompt_modifier": (
            "You are the President taking a phone call from the student. "
            "Practice formal phone etiquette: greeting, stating purpose, "
            "asking questions politely, handling misunderstandings, ending the call. "
            "The student is calling to invite you to an event. "
            "Start by answering the phone formally."
        ),
        "target_vocabulary": [
            "speaking", "regarding", "purpose", "schedule",
            "confirm", "arrangement", "postpone", "follow up",
        ],
        "lesson_goal": "Complete a formal phone conversation with proper etiquette.",
    },
}


def _lessons_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for key, lesson in LESSONS.items():
        buttons.append(
            [InlineKeyboardButton(text=lesson["title"], callback_data=f"lesson:{key}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("lessons"))
@router.message(F.text == "📖 Уроки")
async def cmd_lessons(message: Message) -> None:
    user_id = message.from_user.id
    active = await redis_client.get_active_lesson(user_id)

    if active:
        text = (
            f"You're currently in a lesson: <b>{active['title']}</b>\n\n"
            "Finish it first or use /end_lesson to quit. Nobody quits on Trump though!"
        )
        await message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="End Lesson", callback_data="end_lesson")],
                ]
            ),
        )
        return

    text = (
        "📖 Scenario Lessons -- the best lessons, believe me!\n\n"
        "Pick a lesson and we'll do a role-play scenario. "
        "It's like being in a movie, except you're learning English. Tremendous!"
    )
    await message.answer(text, reply_markup=_lessons_keyboard())


@router.callback_query(lambda c: c.data and c.data.startswith("lesson:"))
async def handle_lesson_pick(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    lesson_key = callback.data.split(":")[1]

    if lesson_key not in LESSONS:
        await callback.answer("Lesson not found!")
        return

    lesson = LESSONS[lesson_key]
    lesson_data = {**lesson, "key": lesson_key}

    await redis_client.set_active_lesson(user_id, lesson_data)
    await redis_client.clear_history(user_id)

    text = (
        f"📖 Starting Lesson: <b>{lesson['title']}</b>\n\n"
        f"{lesson['description']}\n\n"
        f"Goal: {lesson['lesson_goal']}\n\n"
        "Let's begin! Send your first message to start the scenario. "
        "Use /end_lesson when you're done."
    )

    try:
        await callback.message.edit_text(text)
    except Exception:
        await callback.message.answer(text, reply_markup=main_keyboard)

    await callback.answer()


@router.message(Command("end_lesson"))
@router.callback_query(F.data == "end_lesson")
async def handle_end_lesson(event: Message | CallbackQuery) -> None:
    if isinstance(event, CallbackQuery):
        user_id = event.from_user.id
        message = event.message
        await event.answer()
    else:
        user_id = event.from_user.id
        message = event

    active = await redis_client.get_active_lesson(user_id)
    if not active:
        await message.answer(
            "You're not in any lesson right now. Pick one from /lessons!",
            reply_markup=main_keyboard,
        )
        return

    await redis_client.clear_active_lesson(user_id)
    await redis_client.clear_history(user_id)

    old_xp = await redis_client.get_xp(user_id)
    old_title = await redis_client.get_xp_level_title(old_xp)
    new_xp = await redis_client.add_xp(user_id, 30)
    new_title = await redis_client.get_xp_level_title(new_xp)

    text = (
        f"📖 Lesson Complete: <b>{active['title']}</b>\n\n"
        "Fantastic work! You finished the lesson like a true champion. +30 XP!\n\n"
        "Ready for another one? Use /lessons to pick your next adventure!"
    )

    footer = ""
    if new_title != old_title:
        footer += f"\n\n🎉 LEVEL UP! You are now: {new_title}! Tremendous!"

    new_achievements = await check_achievements(user_id)
    footer += format_new_achievements(new_achievements)

    await message.answer(text + footer, reply_markup=main_keyboard)
