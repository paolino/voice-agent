"""End-to-end tests for voice message flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_httpx import HTTPXMock

from voice_agent.bot import VoiceAgentBot
from voice_agent.config import Settings


@pytest.fixture
def e2e_bot(mock_settings: Settings) -> VoiceAgentBot:
    """Create a bot instance for e2e testing."""
    return VoiceAgentBot(mock_settings)


@pytest.mark.e2e
class TestVoiceFlow:
    """End-to-end tests for voice message handling."""

    async def test_full_voice_to_transcription_flow(
        self,
        e2e_bot: VoiceAgentBot,
        httpx_mock: HTTPXMock,
        sample_audio_bytes: bytes,
    ) -> None:
        """Test complete flow from voice to transcription."""
        # Mock whisper server
        httpx_mock.add_response(
            url="http://localhost:8080/transcribe",
            json={"text": "status"},
        )

        # Mock Telegram update
        update = MagicMock()
        update.effective_chat.id = 123
        update.message.voice.file_id = "test-file-id"
        update.message.reply_text = AsyncMock()

        # Mock context with file download
        context = MagicMock()
        mock_file = MagicMock()
        mock_file.download_as_bytearray = AsyncMock(
            return_value=bytearray(sample_audio_bytes)
        )
        context.bot.get_file = AsyncMock(return_value=mock_file)

        # Handle voice message
        await e2e_bot.handle_voice(update, context)

        # Verify transcription was shown
        calls = update.message.reply_text.call_args_list
        assert any("Heard: status" in str(call) for call in calls)

    async def test_permission_approval_flow(
        self,
        e2e_bot: VoiceAgentBot,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test permission request and approval flow."""
        from voice_agent.sessions.permissions import PendingPermission

        # Create session with pending permission
        session = e2e_bot.session_manager.get_or_create(123)
        session.permission_handler.pending = PendingPermission(
            tool_name="Write",
            input_data={"file_path": "/tmp/test.txt"},
        )

        # Mock first voice message (approval)
        httpx_mock.add_response(
            url="http://localhost:8080/transcribe",
            json={"text": "yes"},
        )

        update = MagicMock()
        update.effective_chat.id = 123
        update.message.voice.file_id = "test-file-id"
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        mock_file = MagicMock()
        mock_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"audio"))
        context.bot.get_file = AsyncMock(return_value=mock_file)

        await e2e_bot.handle_voice(update, context)

        # Verify approval was processed
        calls = update.message.reply_text.call_args_list
        assert any("Approved" in str(call) for call in calls)

    async def test_session_switching_flow(
        self,
        e2e_bot: VoiceAgentBot,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test project switching via voice."""
        httpx_mock.add_response(
            url="http://localhost:8080/transcribe",
            json={"text": "switch to whisper"},
        )

        update = MagicMock()
        update.effective_chat.id = 123
        update.message.voice.file_id = "test-file-id"
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        mock_file = MagicMock()
        mock_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"audio"))
        context.bot.get_file = AsyncMock(return_value=mock_file)

        await e2e_bot.handle_voice(update, context)

        # Verify project was switched
        session = e2e_bot.session_manager.get(123)
        assert session is not None
        assert session.cwd == "/code/whisper-server"

    async def test_non_allowed_chat_ignored(
        self,
        e2e_bot: VoiceAgentBot,
    ) -> None:
        """Test that non-allowed chats are ignored."""
        update = MagicMock()
        update.effective_chat.id = 999  # Not in allowed list
        update.message.voice.file_id = "test-file-id"
        update.message.reply_text = AsyncMock()

        context = MagicMock()

        await e2e_bot.handle_voice(update, context)

        # Should not attempt to download or reply
        context.bot.get_file.assert_not_called()
        update.message.reply_text.assert_not_called()

    async def test_transcription_error_handling(
        self,
        e2e_bot: VoiceAgentBot,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test handling of transcription errors."""
        httpx_mock.add_response(
            url="http://localhost:8080/transcribe",
            status_code=500,
        )

        update = MagicMock()
        update.effective_chat.id = 123
        update.message.voice.file_id = "test-file-id"
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        mock_file = MagicMock()
        mock_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"audio"))
        context.bot.get_file = AsyncMock(return_value=mock_file)

        await e2e_bot.handle_voice(update, context)

        # Verify error was reported
        calls = update.message.reply_text.call_args_list
        assert any("Transcription failed" in str(call) for call in calls)

    async def test_download_error_handling(
        self,
        e2e_bot: VoiceAgentBot,
    ) -> None:
        """Test handling of file download errors."""
        update = MagicMock()
        update.effective_chat.id = 123
        update.message.voice.file_id = "test-file-id"
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.bot.get_file = AsyncMock(side_effect=Exception("Download failed"))

        await e2e_bot.handle_voice(update, context)

        # Verify error was reported
        calls = update.message.reply_text.call_args_list
        assert any("Failed to download" in str(call) for call in calls)
