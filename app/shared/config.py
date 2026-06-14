from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "mcp-shared-services"
    app_env: str = "dev"
    database_url: str = "sqlite+aiosqlite:///./mcp_shared_services.db"
    ark_api_key: str | None = None
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    ark_default_model: str = "ep-xxxxxxxx"
    ark_topic_model: str = "ep-xxxxxxxx"
    ark_image_model: str = "doubao-seedream-4-5-251128"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
