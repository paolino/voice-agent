"""End-to-end tests for voice message flow."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_httpx import HTTPXMock

from voice_agent.bot import VoiceAgentBot
from voice_agent.config import Settings


def _make_voice_update(chat_id: int = 123) -> MagicMock:
    """Create a mock Telegram Update for voice messages."""
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.message.voice.file_id = "test-file-id"
    update.message.reply_text = AsyncMock()
    update.message.delete = AsyncMock()
    update.message.chat.send_message = AsyncMock()
    return update


def _make_voice_context(audio: bytes = b"audio") -> MagicMock:
    """Create a mock Telegram context for voice downloads."""
    context = MagicMock()
    mock_file = MagicMock()
    mock_file.download_as_bytearray = AsyncMock(return_value=bytearray(audio))
    context.bot.get_file = AsyncMock(return_value=mock_file)
    return context


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
        httpx_mock.add_response(
            url="http://localhost:8080/transcribe",
            json={"text": "list files in the current directory"},
        )

        update = _make_voice_update()
        context = _make_voice_context(sample_audio_bytes)

        async def mock_send_prompt(*args, **kwargs):  # type: ignore
            yield "Here are the files"

        with patch.object(e2e_bot.session_manager, "send_prompt", mock_send_prompt):
            await e2e_bot.handle_voice(update, context)
            await asyncio.sleep(0.05)

        # Verify transcription echo was shown
        calls = update.message.chat.send_message.call_args_list
        assert any("list files" in str(call) for call in calls)

    async def test_voice_does_not_parse_commands(
        self,
        e2e_bot: VoiceAgentBot,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that voice transcription is never parsed as a command.

        Words like 'status', 'yes', 'cancel' should be sent to Claude
        as prompts, not intercepted as bot commands.
        """
        for word in ("status", "yes", "cancel", "restart", "new session"):
            httpx_mock.add_response(
                url="http://localhost:8080/transcribe",
                json={"text": word},
            )

            update = _make_voice_update()
            context = _make_voice_context()

            captured_prompt = None

            async def mock_send_prompt(
                chat_id: int, prompt: str, **kwargs: object
            ) -> None:
                nonlocal captured_prompt
                captured_prompt = prompt
                yield "ok"  # type: ignore[misc]

            with patch.object(
                e2e_bot.session_manager, "send_prompt", mock_send_prompt
            ):
                await e2e_bot.handle_voice(update, context)
                await asyncio.sleep(0.05)

            assert captured_prompt == word, (
                f"Voice '{word}' should be sent as prompt, not parsed as command"
            )

    async def test_voice_approval_not_intercepted(
        self,
        e2e_bot: VoiceAgentBot,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that saying 'yes' via voice does NOT approve permissions."""
        from voice_agent.sessions.permissions import PendingPermission

        session = e2e_bot.session_manager.get_or_create(123)
        session.permission_handler.pending = PendingPermission(
            tool_name="Write",
            input_data={"file_path": "/tmp/test.txt"},
        )

        httpx_mock.add_response(
            url="http://localhost:8080/transcribe",
            json={"text": "yes"},
        )

        update = _make_voice_update()
        context = _make_voice_context()

        async def mock_send_prompt(*args, **kwargs):  # type: ignore
            yield "ok"

        with patch.object(e2e_bot.session_manager, "send_prompt", mock_send_prompt):
            await e2e_bot.handle_voice(update, context)
            await asyncio.sleep(0.05)

        # Permission should still be pending (not approved by voice)
        assert session.permission_handler.pending is not None

    async def test_non_allowed_chat_ignored(
        self,
        e2e_bot: VoiceAgentBot,
    ) -> None:
        """Test that non-allowed chats are ignored."""
        update = _make_voice_update(chat_id=999)
        context = MagicMock()

        await e2e_bot.handle_voice(update, context)

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

        update = _make_voice_update()
        context = _make_voice_context()

        await e2e_bot.handle_voice(update, context)

        calls = update.message.reply_text.call_args_list
        assert any("Transcription failed" in str(call) for call in calls)

    async def test_download_error_handling(
        self,
        e2e_bot: VoiceAgentBot,
    ) -> None:
        """Test handling of file download errors."""
        update = _make_voice_update()
        context = MagicMock()
        context.bot.get_file = AsyncMock(side_effect=Exception("Download failed"))

        await e2e_bot.handle_voice(update, context)

        calls = update.message.reply_text.call_args_list
        assert any("Failed to download" in str(call) for call in calls)
