import io
import json
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
from bot.prompts import get_system_prompt

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def get_trump_reply(
    history: list[dict],
    level: str = "intermediate",
    topic: str | None = None,
    lesson_context: dict | None = None,
) -> str:
    system_prompt = get_system_prompt(level=level, topic=topic, lesson_context=lesson_context)
    messages = [{"role": "system", "content": system_prompt}] + history

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


async def generate_daily_word(level: str = "intermediate") -> dict:
    level_hints = {
        "beginner": "a simple, common English word suitable for beginners (A1-A2 level)",
        "intermediate": "a useful English word at intermediate level (B1-B2), perhaps a phrasal verb or idiom",
        "advanced": "a sophisticated or nuanced English word for advanced learners (C1-C2)",
    }
    hint = level_hints.get(level, level_hints["intermediate"])

    prompt = (
        f"Pick {hint}. Return a JSON object with exactly these keys:\n"
        "- \"word\": the word or phrase\n"
        "- \"definition\": a clear, simple definition\n"
        "- \"example\": an example sentence using the word\n"
        "- \"task\": a short fun challenge for the student to use this word in a sentence\n"
        "Write everything in Trump's speaking style. Keep it entertaining. Return ONLY valid JSON, no markdown."
    )

    try:
        response = await _client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=1.0,
            max_tokens=300,
        )
        text = response.choices[0].message.content.strip()
        return json.loads(text)
    except (APIError, APITimeoutError) as exc:
        logger.error("OpenAI API error generating daily word: %s", exc)
        raise
    except json.JSONDecodeError:
        logger.error("Failed to parse daily word JSON: %s", text)
        return {
            "word": "tremendous",
            "definition": "Extremely good or impressive. The best word, believe me!",
            "example": "That was a tremendous effort, really fantastic!",
            "task": "Use 'tremendous' in a sentence about something great you did today.",
        }


async def extract_vocabulary(text: str, level: str = "intermediate") -> list[dict]:
    level_hints = {
        "beginner": "very simple but useful words for a beginner (A1-A2)",
        "intermediate": "useful intermediate-level words, phrasal verbs, or idioms (B1-B2)",
        "advanced": "sophisticated or nuanced words for advanced learners (C1-C2)",
    }
    hint = level_hints.get(level, level_hints["intermediate"])

    prompt = (
        f"From the following English text, extract 1-3 interesting or educational words/phrases "
        f"suitable for {hint}. For each word, provide a short Trump-style definition. "
        "Return a JSON array of objects with keys \"word\" and \"definition\". "
        "If no interesting words found, return empty array []. "
        "Return ONLY valid JSON, no markdown.\n\n"
        f"Text: {text}"
    )

    try:
        response = await _client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300,
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        if isinstance(result, list):
            return result
        return []
    except (APIError, APITimeoutError) as exc:
        logger.error("OpenAI API error extracting vocabulary: %s", exc)
        return []
    except json.JSONDecodeError:
        logger.error("Failed to parse vocabulary JSON: %s", raw)
        return []


async def analyze_pronunciation(transcript: str, expected_text: str | None = None) -> str | None:
    context = ""
    if expected_text:
        context = f"The lesson focuses on these target words: {expected_text}. "

    prompt = (
        f"{context}"
        "Analyze this speech-to-text transcription for likely pronunciation issues. "
        "Look for words that may have been mis-transcribed due to pronunciation problems "
        "(e.g., similar-sounding words substituted, missing syllables, wrong stress patterns). "
        "If you find issues, give a SHORT Trump-style pronunciation tip (1-2 sentences max). "
        "If pronunciation seems fine, return exactly: NONE\n\n"
        f"Transcription: {transcript}"
    )

    try:
        response = await _client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150,
        )
        result = response.choices[0].message.content.strip()
        if result.upper() == "NONE":
            return None
        return result
    except (APIError, APITimeoutError) as exc:
        logger.error("OpenAI API error analyzing pronunciation: %s", exc)
        return None


async def generate_quiz(level: str = "intermediate") -> dict:
    level_hints = {
        "beginner": "very simple vocabulary and basic grammar for beginners (A1-A2)",
        "intermediate": "everyday vocabulary, phrasal verbs, or grammar for intermediate learners (B1-B2)",
        "advanced": "advanced vocabulary, idioms, nuanced grammar for advanced learners (C1-C2)",
    }
    hint = level_hints.get(level, level_hints["intermediate"])

    prompt = (
        f"Create a multiple-choice English quiz question using {hint}. "
        "Return a JSON object with exactly these keys:\n"
        "- \"question\": the question text written in Trump's style\n"
        "- \"options\": an object with keys \"A\", \"B\", \"C\", \"D\" and their text values\n"
        "- \"correct\": the letter of the correct answer (A, B, C, or D)\n"
        "- \"explanation\": a short Trump-style explanation of why this is correct\n"
        "Return ONLY valid JSON, no markdown."
    )

    try:
        response = await _client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=1.0,
            max_tokens=400,
        )
        text = response.choices[0].message.content.strip()
        return json.loads(text)
    except (APIError, APITimeoutError) as exc:
        logger.error("OpenAI API error generating quiz: %s", exc)
        raise
    except json.JSONDecodeError:
        logger.error("Failed to parse quiz JSON: %s", text)
        return {
            "question": "What does 'tremendous' mean? Believe me, this is the best question!",
            "options": {
                "A": "Very small",
                "B": "Very large or great",
                "C": "Very slow",
                "D": "Very quiet",
            },
            "correct": "B",
            "explanation": "Tremendous means very large or great. I use it all the time. The best word!",
        }
