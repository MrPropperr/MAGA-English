import io
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
    STT_MODEL,
    TTS_MODEL,
    TTS_VOICE,
)
from bot.prompts import TRUMP_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def get_trump_reply(history: list[dict]) -> str:
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


async def transcribe_voice(audio_bytes: bytes) -> str:
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "voice.ogg"
    transcript = await _client.audio.transcriptions.create(
        model=STT_MODEL,
        file=audio_file,
    )
    return transcript.text.strip()


async def synthesize_speech(text: str) -> bytes:
    response = await _client.audio.speech.create(
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=text,
        response_format="opus",
    )
    return response.content
