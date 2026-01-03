import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://mongo:27017")
    mongo_db: str = os.getenv("MONGO_DB", "vivbliss")
    data_dir: str = os.getenv("DATA_DIR", "/data")

    crawl_spider: str = os.getenv("CRAWL_SPIDER", "products")
    crawl_log: str = os.getenv("CRAWL_LOG", "/data/logs/scrapy.log")

    message_strategy: str = os.getenv("MESSAGE_STRATEGY", "S2")
    telegram_target_chat: str | None = os.getenv("TG_TARGET_CHAT")
    telegram_api_id: int | None = (
        int(os.getenv("TG_API_ID")) if os.getenv("TG_API_ID") else None
    )
    telegram_api_hash: str | None = os.getenv("TG_API_HASH")
    telegram_session_string: str | None = os.getenv("TG_SESSION_STRING")
    telegram_bot_token: str | None = os.getenv("TG_BOT_TOKEN")

    @property
    def celery_broker(self) -> str:
        return self.redis_url

    @property
    def celery_backend(self) -> str:
        return os.getenv("CELERY_BACKEND", self.redis_url)


settings = Settings()
