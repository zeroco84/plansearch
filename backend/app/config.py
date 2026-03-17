"""PlanSearch — Configuration module.

Reads settings from environment variables and provides
typed access throughout the application.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Database
    database_url: str = "postgresql+asyncpg://plansearch:plansearch@postgres/plansearch"
    database_url_sync: str = "postgresql://plansearch:plansearch@postgres/plansearch"

    # Redis
    redis_url: str = "redis://redis:6379"

    # Security
    master_encryption_key: str = ""
    admin_token: str = ""

    # DCC Open Data URLs
    dcc_base_url: str = "https://opendata.dublincity.ie/PandDOpenData/DCC_DUBLINK_BASE.csv"
    dcc_spatial_url: str = "https://opendata.dublincity.ie/PandDOpenData/DCC_PlanApps.csv"
    dcc_appeal_url: str = "https://opendata.dublincity.ie/PandDOpenData/DCC_DUBLINK_APPEAL.csv"
    dcc_furinfo_url: str = "https://opendata.dublincity.ie/PandDOpenData/DCC_DUBLINK_FURINFO.csv"

    # Scraper settings
    scraper_rate_limit_seconds: float = 3.0
    scraper_max_retries: int = 3
    scraper_circuit_breaker_failures: int = 10
    scraper_circuit_breaker_pause_seconds: int = 3600

    # Classifier settings
    classifier_batch_size: int = 100
    classifier_model: str = "claude-haiku-4-5-20251001"

    # App
    app_name: str = "PlanSearch"
    app_version: str = "1.0.0"
    debug: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
