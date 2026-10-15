from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CRAWLOPS_", env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./crawlops.db"
    redis_url: str = "redis://redis:6379/0"
    data_dir: str = "./data"
    admin_email: str = "admin@crawlops.local"
    admin_password: str = ""
    agent_token: str = ""
    encryption_key: str = ""
    session_hours: int = 12
    log_retention_days: int = 30
    source_retention_days: int = 7
    max_archive_bytes: int = 50 * 1024 * 1024
    max_extract_bytes: int = 250 * 1024 * 1024
    max_archive_files: int = 5000


@lru_cache
def settings():
    return Settings()
