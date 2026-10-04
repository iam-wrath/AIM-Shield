"""Settings loaded from environment variables (and the repo-root .env file)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # SecureAI Guard
    guard_url: str = "https://guard.invalid"  # set GUARD_URL in .env
    guard_token: SecretStr  # required; SecretStr keeps it out of repr/logs
    guard_timeout: float = 20.0
    guard_max_retries: int = 3  # retries for 502/503/network errors
    guard_backoff_base: float = 0.5  # seconds; doubles each retry
    guard_max_rate_limit_waits: int = 2
    guard_max_retry_after: float = 65.0  # refuse to sleep longer than this

    # LLM (OpenAI-compatible by default)
    llm_url: str = ""
    llm_key: SecretStr = SecretStr("")
    llm_model: str = ""
    llm_timeout: float = 60.0

    # KwikPay Assist (the system we protect)
    canary_token: str = "KP-REV-7f3a91c2"  # synthetic secret in the system prompt

    # Paths
    rag_dir: str = str(REPO_ROOT / "rag_docs")
    attacks_dir: str = str(REPO_ROOT / "attacks")
    eval_dir: str = str(REPO_ROOT / "eval")
    frontend_dist: str = str(REPO_ROOT / "frontend" / "dist")

    chat_rate_limit_per_min: int = 60  # per client IP on /chat/*; protects Guard quota and LLM spend (0 = off)

    # Local state
    db_path: str = "aim_shield.db"
    session_history_limit: int = 20

    @field_validator("guard_token")
    @classmethod
    def _token_not_blank(cls, v: SecretStr) -> SecretStr:
        if not v.get_secret_value().strip():
            raise ValueError("GUARD_TOKEN is empty")
        return v

    @field_validator("guard_url", "llm_url")
    @classmethod
    def _strip_slash(cls, v: str) -> str:
        return v.strip().rstrip("/")


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        missing = [str(e["loc"][0]).upper() for e in exc.errors() if e["loc"]]
        raise ConfigError(
            f"Invalid configuration: {', '.join(missing)}. "
            "GUARD_TOKEN must be set: copy .env.example to .env and fill it in "
            "(or export the variable). The token is never logged or committed."
        ) from None
