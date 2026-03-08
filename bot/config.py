import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]
OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DAILY_LIMIT: int = int(os.getenv("DAILY_LIMIT", "20"))
HISTORY_PAIRS: int = int(os.getenv("HISTORY_PAIRS", "5"))

OPENAI_MODEL: str = "gpt-4o-mini"
OPENAI_TEMPERATURE: float = 0.95
OPENAI_MAX_TOKENS: int = 150
OPENAI_TOP_P: float = 0.9
OPENAI_FREQUENCY_PENALTY: float = 0.5
OPENAI_PRESENCE_PENALTY: float = 0.3
