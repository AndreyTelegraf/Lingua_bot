from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = Field(default="dev")
    bot_token: str = Field(default="")
    db_path: str = Field(default="./data/lingua.db")
    log_level: str = Field(default="INFO")

    feature_vocab_enabled: bool = Field(default=True)
    feature_level_enabled: bool = Field(default=False)
    feature_ciple_enabled: bool = Field(default=False)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
