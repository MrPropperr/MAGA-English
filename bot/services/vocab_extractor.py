import logging

from bot.services.openai_client import extract_vocabulary
from bot.services.redis_client import redis_client

logger = logging.getLogger(__name__)


async def extract_and_save_vocab(user_id: int, text: str, level: str) -> None:
    try:
        words = await extract_vocabulary(text, level)
        for word_data in words:
            if "word" in word_data and "definition" in word_data:
                await redis_client.save_vocab_word(user_id, word_data)
    except Exception as exc:
        logger.error("Vocab extraction error for user %s: %s", user_id, exc)
