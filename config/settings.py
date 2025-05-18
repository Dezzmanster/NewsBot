import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env
load_dotenv()

# GigaChat Settings
GIGACHAT = {
    "API_KEY": os.getenv('GIGACHAT_API_KEY_CORP') if os.getenv('GIGACHAT_API_KEY_CORP') else os.getenv('GIGACHAT_API_KEY'),
    "MODEL": 'GigaChat-2-Max',
    "VERIFY_SSL": False,
    "SCOPE": 'GIGACHAT_API_CORP' if os.getenv('GIGACHAT_API_KEY_CORP') else 'GIGACHAT_API_PERS',  # Например: GIGACHAT_API_PERS, GIGACHAT_API_B2B, GIGACHAT_API_CORP
}

# Telegram Settings
TELEGRAM = {
    "BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
    "API_ID": os.getenv("TELEGRAM_API_ID"),
    "API_HASH": os.getenv("TELEGRAM_API_HASH"),
    "PHONE": os.getenv("TELEGRAM_PHONE"),
}

# LangSmith / LangChain Tracing
LANGSMITH = {
    "TRACING_V2": os.getenv("LANGCHAIN_TRACING_V2", "false").lower() in ("true", "1", "yes"),
    "API_KEY": os.getenv("LANGCHAIN_API_KEY"),
    "PROJECT": os.getenv("LANGCHAIN_PROJECT", "telegram_news_agents"),
}

# Project Defaults
DEFAULT_LIMIT_PER_CHANNEL = int(os.getenv("DEFAULT_LIMIT_PER_CHANNEL", 10))
MAX_CHANNELS_PER_USER = int(os.getenv("MAX_CHANNELS_PER_USER", 20))