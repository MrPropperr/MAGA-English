import logging

from openai import AsyncOpenAI, APIError, APITimeoutError

from bot.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    OPENAI_MAX_TOKENS,
    OPENAI_TOP_P,
    OPENAI_FREQUENCY_PENALTY,
    OPENAI_PRESENCE_PENALTY,
)
from bot.prompts import TRUMP_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def get_trump_reply(history: list[dict]) -> str:
    """
    Отправляет историю в OpenAI и возвращает ответ Трампа.
    history — список {"role": "user"/"assistant", "content": "..."}
    """
    messages = [{"role": "system", "content": TRUMP_SYSTEM_PROMPT}] + history

    try:
        response = await _client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=OPENAI_TEMPERATURE,
            max_tokens=OPENAI_MAX_TOKENS,
            top_p=OPENAI_TOP_P,
            frequency_penalty=OPENAI_FREQUENCY_PENALTY,
            presence_penalty=OPENAI_PRESENCE_PENALTY,
        )
        return response.choices[0].message.content.strip()
    except (APIError, APITimeoutError) as exc:
        logger.error("OpenAI API error: %s", exc)
        raise
