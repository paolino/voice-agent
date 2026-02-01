"""Unit tests for configuration loading."""

import os

import pytest

from voice_agent.config import Settings, load_settings


class TestSettings:
    """Tests for Settings class."""

    def test_get_allowed_chat_ids_single(self) -> None:
        """Test parsing single chat ID."""
        settings = Settings(
            telegram_bot_token="token",
            allowed_chat_ids="123",
        )
        assert settings.get_allowed_chat_ids() == {123}

    def test_get_allowed_chat_ids_multiple(self) -> None:
        """Test parsing multiple chat IDs."""
        settings = Settings(
            telegram_bot_token="token",
            allowed_chat_ids="123,456,789",
        )
        assert settings.get_allowed_chat_ids() == {123, 456, 789}

    def test_get_allowed_chat_ids_with_spaces(self) -> None:
        """Test parsing chat IDs with spaces."""
        settings = Settings(
            telegram_bot_token="token",
            allowed_chat_ids="123, 456, 789",
        )
        assert settings.get_allowed_chat_ids() == {123, 456, 789}

    def test_get_allowed_chat_ids_empty(self) -> None:
        """Test empty allowed chat IDs."""
        settings = Settings(
            telegram_bot_token="token",
            allowed_chat_ids="",
        )
        assert settings.get_allowed_chat_ids() == set()

    def test_default_values(self) -> None:
        """Test default values are applied."""
        settings = Settings(
            telegram_bot_token="token",
        )
        assert settings.whisper_url == "http://localhost:8080/transcribe"
        assert settings.default_cwd == "/code"
        assert settings.permission_timeout == 300
        assert settings.projects == {}

    def test_projects_dict(self) -> None:
        """Test projects dictionary."""
        settings = Settings(
            telegram_bot_token="token",
            projects={"proj1": "/path/1", "proj2": "/path/2"},
        )
        assert settings.projects == {"proj1": "/path/1", "proj2": "/path/2"}


@pytest.mark.unit
class TestLoadSettings:
    """Tests for load_settings function."""

    def test_load_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading settings from environment variables."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
        monkeypatch.setenv("WHISPER_URL", "http://custom:9000/transcribe")
        monkeypatch.setenv("ALLOWED_CHAT_IDS", "111,222")

        settings = load_settings()

        assert settings.telegram_bot_token == "test-token"
        assert settings.whisper_url == "http://custom:9000/transcribe"
        assert settings.get_allowed_chat_ids() == {111, 222}

    def test_missing_required_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that missing required fields raise error."""
        # Clear any existing env vars
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

        with pytest.raises(Exception):  # ValidationError
            load_settings()
