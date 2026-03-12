import json
from datetime import datetime, timezone

import redis.asyncio as aioredis

from bot.config import DAILY_LIMIT, HISTORY_PAIRS, REDIS_URL

HISTORY_MAX = HISTORY_PAIRS * 2
KEY_PREFIX = "trump_bot:user"


def _history_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:history"


def _requests_key(user_id: int) -> str:
    return f"{KEY_PREFIX}:{user_id}:requests_today"


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
        return await self.get_requests_today(user_id) >= DAILY_LIMIT

    async def save_tts_text(self, message_id: int, text: str) -> None:
        key = f"trump_bot:tts:{message_id}"
        await self.r.set(key, text, ex=3600)

    async def get_tts_text(self, message_id: int) -> str | None:
        return await self.r.get(f"trump_bot:tts:{message_id}")


redis_client = RedisClient()
