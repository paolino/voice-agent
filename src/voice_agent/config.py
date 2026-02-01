"""Configuration management for voice-agent.

Loads settings from environment variables with validation.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        telegram_bot_token: Telegram Bot API token from @BotFather.
        whisper_url: URL of the whisper-server transcription endpoint.
        allowed_chat_ids: Comma-separated list of allowed Telegram chat IDs.
        default_cwd: Default working directory for Claude sessions.
        permission_timeout: Seconds to wait for permission approval.
        projects: Mapping of project names to their working directories.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = Field(
        description="Telegram Bot API token from @BotFather"
    )
    whisper_url: str = Field(
        default="http://localhost:8080/transcribe",
        description="URL of the whisper-server transcription endpoint",
    )
    allowed_chat_ids: str = Field(
        default="",
        description="Comma-separated list of allowed Telegram chat IDs",
    )
    default_cwd: str = Field(
        default="/code",
        description="Default working directory for Claude sessions",
    )
    permission_timeout: int = Field(
        default=300,
        description="Seconds to wait for permission approval",
    )
    projects: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of project names to their working directories",
    )
    session_storage_path: str = Field(
        default="sessions.json",
        description="Path to the session storage file",
    )

    def get_allowed_chat_ids(self) -> set[int]:
        """Parse allowed_chat_ids into a set of integers.

        Returns:
            Set of allowed Telegram chat IDs.
        """
        if not self.allowed_chat_ids:
            return set()
        return {int(cid.strip()) for cid in self.allowed_chat_ids.split(",")}


def load_settings() -> Settings:
    """Load and validate settings from environment.

    Returns:
        Validated Settings instance.

    Raises:
        ValidationError: If required settings are missing or invalid.
    """
    return Settings()
