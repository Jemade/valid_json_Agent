from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Agent & Retry Settings
    default_provider: str = "mock"
    default_model: str = "gpt-4o-mini"
    max_retries: int = Field(default=3, ge=1, le=10)
    request_timeout_seconds: float = Field(default=30.0, gt=0)
    extraction_timeout_seconds: float = Field(default=90.0, gt=0)
    max_concurrent_extractions: int = Field(default=16, ge=1)
    admission_timeout_seconds: float = Field(default=1.0, gt=0)
    max_http_connections: int = Field(default=32, ge=1)

    # Privacy & Logging
    log_raw_input: bool = False
    log_raw_output: bool = False
    log_level: str = "INFO"

    # Upstream Providers
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com/v1"

    environment: str = "development"


settings = Settings()
