"""Shared test fixtures for voice-agent."""

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from voice_agent.config import Settings
from voice_agent.sessions import PermissionHandler, SessionManager


@pytest.fixture
def mock_settings(tmp_path: Any) -> Settings:
    """Create mock settings for testing."""
    return Settings(
        telegram_bot_token="test-token",
        whisper_url="http://localhost:8080/transcribe",
        allowed_chat_ids="123,456",
        default_cwd="/code",
        permission_timeout=10,
        projects={"whisper": "/code/whisper-server", "agent": "/code/voice-agent"},
        session_storage_path=str(tmp_path / "test_sessions.json"),
    )


@pytest.fixture
def session_manager(mock_settings: Settings) -> SessionManager:
    """Create a session manager for testing."""
    return SessionManager(
        default_cwd=mock_settings.default_cwd,
        permission_timeout=mock_settings.permission_timeout,
    )


@pytest.fixture
def permission_handler() -> PermissionHandler:
    """Create a permission handler for testing."""
    return PermissionHandler(timeout=5)


@pytest.fixture
def mock_telegram_update() -> MagicMock:
    """Create a mock Telegram Update with voice message."""
    update = MagicMock()
    update.effective_chat.id = 123
    update.message.voice.file_id = "test-file-id"
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_telegram_context() -> MagicMock:
    """Create a mock Telegram context."""
    context = MagicMock()
    context.bot.get_file = AsyncMock()

    mock_file = MagicMock()
    mock_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"audio data"))
    context.bot.get_file.return_value = mock_file

    return context


@pytest.fixture
def sample_audio_bytes() -> bytes:
    """Sample audio bytes for testing."""
    return b"OggS\x00\x02" + b"\x00" * 100  # Minimal OGG header


@pytest.fixture
def mock_whisper_response() -> dict[str, Any]:
    """Mock whisper-server response."""
    return {"text": "list files in current directory"}


class MockClaudeSession:
    """Mock Claude SDK session for testing."""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.responses: list[str] = [
            "Here are the files in the current directory:",
            "- file1.py",
            "- file2.py",
        ]

    async def send_prompt(self, prompt: str) -> AsyncIterator[str]:
        """Mock sending a prompt."""
        self.prompts.append(prompt)
        for response in self.responses:
            yield response


@pytest.fixture
def mock_claude_session() -> MockClaudeSession:
    """Create a mock Claude session."""
    return MockClaudeSession()
