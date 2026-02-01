"""Integration tests for bot handlers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from voice_agent.bot import VoiceAgentBot
from voice_agent.config import Settings


@pytest.fixture
def bot(mock_settings: Settings) -> VoiceAgentBot:
    """Create a bot instance for testing."""
    return VoiceAgentBot(mock_settings)


@pytest.mark.integration
class TestVoiceAgentBot:
    """Integration tests for VoiceAgentBot."""

    def test_is_allowed_with_whitelist(self, bot: VoiceAgentBot) -> None:
        """Test whitelist enforcement."""
        assert bot.is_allowed(123) is True
        assert bot.is_allowed(456) is True
        assert bot.is_allowed(999) is False

    def test_is_allowed_empty_whitelist(self, mock_settings: Settings) -> None:
        """Test empty whitelist allows all."""
        mock_settings.allowed_chat_ids = ""
        test_bot = VoiceAgentBot(mock_settings)

        assert test_bot.is_allowed(123) is True
        assert test_bot.is_allowed(999) is True

    async def test_start_command_allowed(self, bot: VoiceAgentBot) -> None:
        """Test /start command for allowed chat."""
        update = MagicMock()
        update.effective_chat.id = 123
        update.message.reply_text = AsyncMock()

        await bot.start_command(update, MagicMock())

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "Voice Agent ready" in call_args

    async def test_start_command_not_allowed(self, bot: VoiceAgentBot) -> None:
        """Test /start command for non-allowed chat."""
        update = MagicMock()
        update.effective_chat.id = 999
        update.message.reply_text = AsyncMock()

        await bot.start_command(update, MagicMock())

        update.message.reply_text.assert_not_called()

    async def test_status_command_no_session(self, bot: VoiceAgentBot) -> None:
        """Test /status command without active session."""
        update = MagicMock()
        update.effective_chat.id = 123
        update.message.reply_text = AsyncMock()

        await bot.status_command(update, MagicMock())

        update.message.reply_text.assert_called_once_with("No active session.")

    async def test_status_command_with_session(self, bot: VoiceAgentBot) -> None:
        """Test /status command with active session."""
        # Create a session first
        bot.session_manager.get_or_create(123)

        update = MagicMock()
        update.effective_chat.id = 123
        update.message.reply_text = AsyncMock()

        await bot.status_command(update, MagicMock())

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "Working directory" in call_args

    async def test_handle_transcription_approve(self, bot: VoiceAgentBot) -> None:
        """Test handling approval transcription."""
        # Create session with pending permission
        from voice_agent.sessions.permissions import PendingPermission

        session = bot.session_manager.get_or_create(123)
        session.permission_handler.pending = PendingPermission(
            tool_name="Write", input_data={}
        )

        update = MagicMock()
        update.effective_chat.id = 123
        update.message.reply_text = AsyncMock()

        await bot._handle_transcription(123, "yes", update)

        update.message.reply_text.assert_called_once_with("Approved.")

    async def test_handle_transcription_reject(self, bot: VoiceAgentBot) -> None:
        """Test handling rejection transcription."""
        from voice_agent.sessions.permissions import PendingPermission

        session = bot.session_manager.get_or_create(123)
        session.permission_handler.pending = PendingPermission(
            tool_name="Write", input_data={}
        )

        update = MagicMock()
        update.effective_chat.id = 123
        update.message.reply_text = AsyncMock()

        await bot._handle_transcription(123, "no", update)

        update.message.reply_text.assert_called_once_with("Rejected.")

    async def test_handle_transcription_new_session(self, bot: VoiceAgentBot) -> None:
        """Test handling new session request."""
        # Create existing session
        old_session = bot.session_manager.get_or_create(123)
        old_session.message_count = 10

        update = MagicMock()
        update.effective_chat.id = 123
        update.message.reply_text = AsyncMock()

        await bot._handle_transcription(123, "new session", update)

        update.message.reply_text.assert_called_once_with("Started new session.")
        new_session = bot.session_manager.get(123)
        assert new_session is not None
        assert new_session.message_count == 0

    async def test_handle_transcription_switch_project(
        self, bot: VoiceAgentBot
    ) -> None:
        """Test handling project switch."""
        update = MagicMock()
        update.effective_chat.id = 123
        update.message.reply_text = AsyncMock()

        await bot._handle_transcription(123, "work on whisper", update)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "Switched to whisper" in call_args

    async def test_handle_transcription_unknown_project(
        self, bot: VoiceAgentBot
    ) -> None:
        """Test handling unknown project falls through to prompt."""
        import asyncio
        from unittest.mock import patch

        update = MagicMock()
        update.effective_chat.id = 123
        update.message.reply_text = AsyncMock()

        # Mock send_prompt to return immediately
        async def mock_send_prompt(*args, **kwargs):
            yield "test response"

        with patch.object(bot.session_manager, "send_prompt", mock_send_prompt):
            await bot._handle_transcription(123, "work on unknown", update)
            # Give background task time to complete
            await asyncio.sleep(0.05)

        # Should have sent response from prompt
        update.message.reply_text.assert_called()

    async def test_handle_text_allowed(self, bot: VoiceAgentBot) -> None:
        """Test text message handling for allowed chat."""
        update = MagicMock()
        update.effective_chat.id = 123
        update.message.text = "status"
        update.message.reply_text = AsyncMock()

        await bot.handle_text(update, MagicMock())

        # Status should be returned
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "Working directory" in call_args or "No active session" in call_args

    async def test_handle_text_not_allowed(self, bot: VoiceAgentBot) -> None:
        """Test text message handling for non-allowed chat."""
        update = MagicMock()
        update.effective_chat.id = 999
        update.message.text = "hello"
        update.message.reply_text = AsyncMock()

        await bot.handle_text(update, MagicMock())

        update.message.reply_text.assert_not_called()

    async def test_handle_text_approve(self, bot: VoiceAgentBot) -> None:
        """Test text approval handling."""
        from voice_agent.sessions.permissions import PendingPermission

        session = bot.session_manager.get_or_create(123)
        session.permission_handler.pending = PendingPermission(
            tool_name="Write", input_data={}
        )

        update = MagicMock()
        update.effective_chat.id = 123
        update.message.text = "yes"
        update.message.reply_text = AsyncMock()

        await bot.handle_text(update, MagicMock())

        update.message.reply_text.assert_called_once_with("Approved.")

    async def test_handle_text_no_message(self, bot: VoiceAgentBot) -> None:
        """Test text handler with missing message."""
        update = MagicMock()
        update.effective_chat = None
        update.message = None

        # Should return early without error
        await bot.handle_text(update, MagicMock())
