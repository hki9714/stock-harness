from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(..., env="TELEGRAM_CHAT_ID")

    watch_list: str = Field("005930,000660", env="WATCH_LIST")
    volume_surge_ratio: float = Field(3.0, env="VOLUME_SURGE_RATIO")
    price_surge_pct: float = Field(5.0, env="PRICE_SURGE_PCT")
    sentiment_positive_threshold: float = Field(0.65, env="SENTIMENT_POSITIVE_THRESHOLD")
    sentiment_surge_count: int = Field(20, env="SENTIMENT_SURGE_COUNT")
    check_interval_minutes: int = Field(30, env="CHECK_INTERVAL_MINUTES")
    price_drop_pct: float = Field(5.0, env="PRICE_DROP_PCT")

    anthropic_api_key: str = Field("", env="ANTHROPIC_API_KEY")
    default_provider: str = Field("claude", env="DEFAULT_PROVIDER")
    default_model: str = Field("claude-sonnet-4-6", env="DEFAULT_MODEL")
    git_auto_commit: str = Field("false", env="GIT_AUTO_COMMIT")
    git_auto_commit_delay: int = Field(10, env="GIT_AUTO_COMMIT_DELAY")
    runtime: str = Field("local", env="RUNTIME")

    @property
    def watch_codes(self) -> List[str]:
        return [c.strip() for c in self.watch_list.split(",")]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()