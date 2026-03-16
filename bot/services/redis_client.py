import base64
import json
import time
from datetime import datetime, timezone

import redis.asyncio as aioredis

from bot.config import DAILY_LIMIT, HISTORY_PAIRS, REDIS_URL

HISTORY_MAX = HISTORY_PAIRS * 2
KEY_PREFIX = "trump_bot:user"

XP_LEVELS = [
    (0, "Intern"),
    (100, "Associate"),
    (300, "Vice President"),
    (600, "Executive"),
    (1000, "President"),
]


def _history_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:history"


def _requests_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:requests_today"


def _level_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:level"


def _streak_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:streak"


def _last_active_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:last_active"


def _topic_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:topic"


def _total_messages_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:total_messages"


def _daily_word_key(date: str) -> str:
    return f"trump_bot:daily_word:{date}"


def _premium_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:premium_until"


def _referred_by_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:referred_by"


def _referrals_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:referrals"


def _bonus_messages_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:bonus_messages"


def _xp_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:xp"


def _username_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:username"


def _achievements_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:achievements"


def _quiz_correct_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:quiz_correct"


def _quiz_total_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:quiz_total"


def _voice_count_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:voice_count"


def _daily_word_count_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:daily_word_count"


def _seconds_until_midnight_utc() -> int:
    now = datetime.now(timezone.utc)
    seconds_passed = now.hour * 3600 + now.minute * 60 + now.second
    return max(1, 86400 - seconds_passed)


class RedisClient:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()

    @property
    def r(self) -> aioredis.Redis:
        assert self._redis is not None, "Redis not connected"
        return self._redis

    async def get_history(self, user_id: int) -> list[dict]:
        raw = await self.r.lrange(_history_key(user_id), 0, -1)
        return [json.loads(item) for item in raw]

    async def append_message(self, user_id: int, role: str, content: str) -> None:
        key = _history_key(user_id)
        await self.r.rpush(key, json.dumps({"role": role, "content": content}))
        await self.r.ltrim(key, -HISTORY_MAX, -1)

    async def clear_history(self, user_id: int) -> None:
        await self.r.delete(_history_key(user_id))

    async def get_requests_today(self, user_id: int) -> int:
        val = await self.r.get(_requests_key(user_id))
        return int(val) if val else 0

    async def increment_requests(self, user_id: int) -> int:
        key = _requests_key(user_id)
        count = await self.r.incr(key)
        if count == 1:
            ttl = _seconds_until_midnight_utc()
            await self.r.expire(key, ttl)
        return count

    async def is_limit_exceeded(self, user_id: int) -> bool:
        if await self.is_premium(user_id):
            return False
        bonus = await self.get_bonus_messages(user_id)
        current = await self.get_requests_today(user_id)
        return current >= DAILY_LIMIT + bonus

    async def get_effective_limit(self, user_id: int) -> int:
        bonus = await self.get_bonus_messages(user_id)
        return DAILY_LIMIT + bonus

    async def save_tts_text(self, message_id: int, text: str) -> None:
        await self.r.set(f"trump_bot:tts:text:{message_id}", text, ex=3600)

    async def get_tts_text(self, message_id: int) -> str | None:
        return await self.r.get(f"trump_bot:tts:text:{message_id}")

    async def save_tts_audio(self, message_id: int, audio: bytes) -> None:
        encoded = base64.b64encode(audio).decode("ascii")
        await self.r.set(f"trump_bot:tts:audio:{message_id}", encoded, ex=3600)

    async def get_tts_audio(self, message_id: int) -> bytes | None:
        encoded = await self.r.get(f"trump_bot:tts:audio:{message_id}")
        if encoded:
            return base64.b64decode(encoded)
        return None

    async def get_level(self, user_id: int) -> str:
        val = await self.r.get(_level_key(user_id))
        return val if val else "intermediate"

    async def set_level(self, user_id: int, level: str) -> None:
        await self.r.set(_level_key(user_id), level)

    async def get_topic(self, user_id: int) -> str | None:
        return await self.r.get(_topic_key(user_id))

    async def set_topic(self, user_id: int, topic: str) -> None:
        await self.r.set(_topic_key(user_id), topic)

    async def update_streak(self, user_id: int) -> int:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        last_active = await self.r.get(_last_active_key(user_id))

        if last_active == today:
            streak = await self.r.get(_streak_key(user_id))
            return int(streak) if streak else 1

        from datetime import timedelta
        yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

        if last_active == yesterday_str:
            streak = await self.r.incr(_streak_key(user_id))
        else:
            streak = 1
            await self.r.set(_streak_key(user_id), "1")

        await self.r.set(_last_active_key(user_id), today)
        return int(streak)

    async def get_streak(self, user_id: int) -> int:
        val = await self.r.get(_streak_key(user_id))
        return int(val) if val else 0

    async def increment_total_messages(self, user_id: int) -> int:
        return await self.r.incr(_total_messages_key(user_id))

    async def get_total_messages(self, user_id: int) -> int:
        val = await self.r.get(_total_messages_key(user_id))
        return int(val) if val else 0

    async def get_daily_word(self, date: str) -> dict | None:
        val = await self.r.get(_daily_word_key(date))
        if val:
            return json.loads(val)
        return None

    async def save_daily_word(self, date: str, word_data: dict) -> None:
        await self.r.set(_daily_word_key(date), json.dumps(word_data), ex=86400)

    async def activate_premium(self, user_id: int, days: int) -> None:
        now = int(time.time())
        current = await self.r.get(_premium_key(user_id))
        if current and int(current) > now:
            start = int(current)
        else:
            start = now
        new_until = start + days * 86400
        await self.r.set(_premium_key(user_id), str(new_until))

    async def is_premium(self, user_id: int) -> bool:
        val = await self.r.get(_premium_key(user_id))
        if not val:
            return False
        return int(val) > int(time.time())

    async def get_premium_until(self, user_id: int) -> int | None:
        val = await self.r.get(_premium_key(user_id))
        if val and int(val) > int(time.time()):
            return int(val)
        return None

    async def set_referred_by(self, user_id: int, referrer_id: int) -> None:
        await self.r.set(_referred_by_key(user_id), str(referrer_id))

    async def get_referred_by(self, user_id: int) -> int | None:
        val = await self.r.get(_referred_by_key(user_id))
        return int(val) if val else None

    async def increment_referrals(self, user_id: int) -> int:
        return await self.r.incr(_referrals_key(user_id))

    async def get_referrals(self, user_id: int) -> int:
        val = await self.r.get(_referrals_key(user_id))
        return int(val) if val else 0

    async def add_bonus_messages(self, user_id: int, count: int) -> int:
        return await self.r.incrby(_bonus_messages_key(user_id), count)

    async def get_bonus_messages(self, user_id: int) -> int:
        val = await self.r.get(_bonus_messages_key(user_id))
        return int(val) if val else 0

    async def add_xp(self, user_id: int, amount: int) -> int:
        new_total = await self.r.incrby(_xp_key(user_id), amount)
        await self.r.zadd("trump_bot:leaderboard", {str(user_id): new_total})
        return new_total

    async def get_xp(self, user_id: int) -> int:
        val = await self.r.get(_xp_key(user_id))
        return int(val) if val else 0

    async def get_xp_level(self, user_id: int) -> tuple[str, int, int]:
        xp = await self.get_xp(user_id)
        title = XP_LEVELS[0][1]
        next_level_xp = XP_LEVELS[1][0] if len(XP_LEVELS) > 1 else 0
        for i, (threshold, name) in enumerate(XP_LEVELS):
            if xp >= threshold:
                title = name
                if i + 1 < len(XP_LEVELS):
                    next_level_xp = XP_LEVELS[i + 1][0]
                else:
                    next_level_xp = 0
        return title, xp, next_level_xp

    async def get_xp_level_title(self, xp: int) -> str:
        title = XP_LEVELS[0][1]
        for threshold, name in XP_LEVELS:
            if xp >= threshold:
                title = name
        return title

    async def save_username(self, user_id: int, username: str) -> None:
        await self.r.set(_username_key(user_id), username)

    async def get_username(self, user_id: int) -> str | None:
        return await self.r.get(_username_key(user_id))

    async def get_leaderboard(self, count: int = 10) -> list[tuple[str, float]]:
        return await self.r.zrevrange("trump_bot:leaderboard", 0, count - 1, withscores=True)

    async def get_leaderboard_rank(self, user_id: int) -> int | None:
        rank = await self.r.zrevrank("trump_bot:leaderboard", str(user_id))
        if rank is not None:
            return rank + 1
        return None

    async def grant_achievement(self, user_id: int, key: str) -> bool:
        return await self.r.sadd(_achievements_key(user_id), key) == 1

    async def get_achievements(self, user_id: int) -> set[str]:
        return await self.r.smembers(_achievements_key(user_id))

    async def has_achievement(self, user_id: int, key: str) -> bool:
        return await self.r.sismember(_achievements_key(user_id), key)

    async def save_quiz_answer(self, user_id: int, message_id: int, answer: str) -> None:
        await self.r.set(f"trump_bot:quiz:{user_id}:{message_id}", answer, ex=3600)

    async def get_quiz_answer(self, user_id: int, message_id: int) -> str | None:
        return await self.r.get(f"trump_bot:quiz:{user_id}:{message_id}")

    async def increment_quiz_correct(self, user_id: int) -> int:
        return await self.r.incr(_quiz_correct_key(user_id))

    async def increment_quiz_total(self, user_id: int) -> int:
        return await self.r.incr(_quiz_total_key(user_id))

    async def get_quiz_stats(self, user_id: int) -> tuple[int, int]:
        correct = await self.r.get(_quiz_correct_key(user_id))
        total = await self.r.get(_quiz_total_key(user_id))
        return int(correct) if correct else 0, int(total) if total else 0

    async def increment_voice_count(self, user_id: int) -> int:
        return await self.r.incr(_voice_count_key(user_id))

    async def get_voice_count(self, user_id: int) -> int:
        val = await self.r.get(_voice_count_key(user_id))
        return int(val) if val else 0

    async def increment_daily_word_count(self, user_id: int) -> int:
        return await self.r.incr(_daily_word_count_key(user_id))

    async def get_daily_word_count(self, user_id: int) -> int:
        val = await self.r.get(_daily_word_count_key(user_id))
        return int(val) if val else 0


    async def save_vocab_word(self, user_id: int, word_data: dict) -> None:
        key = f"{KEY_PREFIX}:{user_id}:vocab"
        now = int(time.time())
        review_at = now + 86400
        word_data["interval"] = 1
        member = json.dumps(word_data, ensure_ascii=False)
        existing = await self.r.zscore(key, member)
        if existing is None:
            await self.r.zadd(key, {member: review_at})

    async def get_due_words(self, user_id: int, limit: int = 1) -> list[dict]:
        key = f"{KEY_PREFIX}:{user_id}:vocab"
        now = int(time.time())
        raw = await self.r.zrangebyscore(key, 0, now, start=0, num=limit)
        return [json.loads(item) for item in raw]

    async def update_word_interval(self, user_id: int, word_data: dict, correct: bool) -> None:
        key = f"{KEY_PREFIX}:{user_id}:vocab"
        old_member = json.dumps(word_data, ensure_ascii=False)
        await self.r.zrem(key, old_member)
        if correct:
            word_data["interval"] = min(word_data.get("interval", 1) * 2, 16)
        else:
            word_data["interval"] = 1
        now = int(time.time())
        review_at = now + word_data["interval"] * 86400
        new_member = json.dumps(word_data, ensure_ascii=False)
        await self.r.zadd(key, {new_member: review_at})

    async def get_vocab_count(self, user_id: int) -> int:
        key = f"{KEY_PREFIX}:{user_id}:vocab"
        return await self.r.zcard(key)

    async def get_vocab_due_count(self, user_id: int) -> int:
        key = f"{KEY_PREFIX}:{user_id}:vocab"
        now = int(time.time())
        return await self.r.zcount(key, 0, now)

    async def get_active_lesson(self, user_id: int) -> dict | None:
        val = await self.r.get(f"{KEY_PREFIX}:{user_id}:active_lesson")
        if val:
            return json.loads(val)
        return None

    async def set_active_lesson(self, user_id: int, lesson_data: dict) -> None:
        await self.r.set(
            f"{KEY_PREFIX}:{user_id}:active_lesson",
            json.dumps(lesson_data, ensure_ascii=False),
            ex=86400,
        )

    async def clear_active_lesson(self, user_id: int) -> None:
        await self.r.delete(f"{KEY_PREFIX}:{user_id}:active_lesson")


redis_client = RedisClient()
