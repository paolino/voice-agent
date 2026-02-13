"""Integration tests for bot handlers."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

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
        """Test handling approval transcription (silent - no feedback)."""
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

        # Silent approval - no message sent
        update.message.reply_text.assert_not_called()

    async def test_handle_transcription_reject(self, bot: VoiceAgentBot) -> None:
        """Test handling rejection transcription."""
        from voice_agent.sessions.permissions import PendingPermission

        session = bot.session_manager.get_or_create(123)
        session.permission_handler.pending = PendingPermission(
            tool_name="Write", input_data={"file_path": "/tmp/test.txt"}
        )

        update = MagicMock()
        update.effective_chat.id = 123
        update.message.reply_text = AsyncMock()

        await bot._handle_transcription(123, "no", update)

        update.message.reply_text.assert_called_once_with(
            "❌ <b>Rejected:</b> Write file: /tmp/test.txt", parse_mode="HTML"
        )

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
        """Test text approval handling (silent - no feedback)."""
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

        # Silent approval - no message sent
        update.message.reply_text.assert_not_called()

    async def test_handle_text_no_message(self, bot: VoiceAgentBot) -> None:
        """Test text handler with missing message."""
        update = MagicMock()
        update.effective_chat = None
        update.message = None

        # Should return early without error
        await bot.handle_text(update, MagicMock())

    async def test_handle_transcription_restart_shows_confirmation(
        self, bot: VoiceAgentBot
    ) -> None:
        """Test handling restart request shows confirmation dialog."""
        from voice_agent.sessions.permissions import StickyApproval

        # Create existing session with sticky approvals
        session = bot.session_manager.get_or_create(123)
        session.message_count = 10
        session.permission_handler.sticky_approvals.append(
            StickyApproval(tool_name="Bash", pattern={"command": "ls"})
        )

        update = MagicMock()
        update.effective_chat.id = 123
        update.message.reply_text = AsyncMock()

        await bot._handle_transcription(123, "restart", update)

        # Should show confirmation dialog, not immediate restart
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert "Are you sure" in call_args[0][0]
        assert "1 auto-approval" in call_args[0][0]
        assert "reply_markup" in call_args[1]

        # Session should NOT be reset yet
        same_session = bot.session_manager.get(123)
        assert same_session.message_count == 10
        assert len(same_session.permission_handler.sticky_approvals) == 1

    async def test_restart_confirm_callback(self, bot: VoiceAgentBot) -> None:
        """Test confirm_restart callback actually restarts."""
        from voice_agent.sessions.permissions import StickyApproval

        # Create existing session with sticky approvals
        session = bot.session_manager.get_or_create(123)
        session.message_count = 10
        session.permission_handler.sticky_approvals.append(
            StickyApproval(tool_name="Bash", pattern={"command": "ls"})
        )

        update = MagicMock()
        query = MagicMock()
        query.data = "confirm_restart"
        query.message.chat.id = 123
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        await bot.handle_callback(update, MagicMock())

        # Should have restarted
        query.edit_message_text.assert_called_once()
        call_args = query.edit_message_text.call_args[0][0]
        assert "Restarted" in call_args
        assert "Cleared 1 auto-approval" in call_args

        # Session should be reset
        new_session = bot.session_manager.get(123)
        assert new_session.message_count == 0
        assert len(new_session.permission_handler.sticky_approvals) == 0

    async def test_restart_cancel_callback(self, bot: VoiceAgentBot) -> None:
        """Test cancel_restart callback cancels restart."""
        # Create existing session
        session = bot.session_manager.get_or_create(123)
        session.message_count = 5

        update = MagicMock()
        query = MagicMock()
        query.data = "cancel_restart"
        query.message.chat.id = 123
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        await bot.handle_callback(update, MagicMock())

        query.edit_message_text.assert_called_once_with("Restart cancelled.")

        # Session should NOT be reset
        same_session = bot.session_manager.get(123)
        assert same_session.message_count == 5

    async def test_restart_command(self, bot: VoiceAgentBot) -> None:
        """Test /restart command shows confirmation."""
        # Create existing session
        session = bot.session_manager.get_or_create(123)
        session.message_count = 5

        update = MagicMock()
        update.effective_chat.id = 123
        update.message.reply_text = AsyncMock()

        await bot.restart_command(update, MagicMock())

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert "Are you sure" in call_args[0][0]

        # Session should NOT be reset yet
        same_session = bot.session_manager.get(123)
        assert same_session.message_count == 5

    async def test_restart_command_not_allowed(self, bot: VoiceAgentBot) -> None:
        """Test /restart command for non-allowed chat."""
        update = MagicMock()
        update.effective_chat.id = 999
        update.message.reply_text = AsyncMock()

        await bot.restart_command(update, MagicMock())

        update.message.reply_text.assert_not_called()


@pytest.mark.integration
class TestPhotoHandler:
    """Tests for photo/image message handling."""

    async def test_handle_photo_basic(
        self,
        bot: VoiceAgentBot,
        mock_telegram_photo_update: MagicMock,
        mock_telegram_photo_context: MagicMock,
    ) -> None:
        """Test photo with caption sends image prompt."""

        async def mock_send_prompt(
            chat_id: int, prompt: str, **kwargs: object
        ) -> None:
            # Verify images were passed
            images = kwargs.get("images")
            assert images is not None
            assert len(images) == 1
            assert images[0].media_type == "image/jpeg"
            assert len(images[0].data) > 0
            yield "I see an image"  # type: ignore[misc]

        with patch.object(bot.session_manager, "send_prompt", mock_send_prompt):
            await bot.handle_photo(
                mock_telegram_photo_update, mock_telegram_photo_context
            )
            await asyncio.sleep(0.05)

        # Should have downloaded the largest photo
        mock_telegram_photo_context.bot.get_file.assert_called_once_with(
            "large-photo-id"
        )

    async def test_handle_photo_no_caption(
        self,
        bot: VoiceAgentBot,
        mock_telegram_photo_context: MagicMock,
    ) -> None:
        """Test photo without caption uses default prompt."""
        update = MagicMock()
        update.effective_chat.id = 123
        update.message.photo = [MagicMock(file_id="photo-id")]
        update.message.caption = None
        update.message.document = None
        update.message.reply_text = AsyncMock()

        captured_prompt = None

        async def mock_send_prompt(
            chat_id: int, prompt: str, **kwargs: object
        ) -> None:
            nonlocal captured_prompt
            captured_prompt = prompt
            yield "Description"  # type: ignore[misc]

        with patch.object(bot.session_manager, "send_prompt", mock_send_prompt):
            await bot.handle_photo(update, mock_telegram_photo_context)
            await asyncio.sleep(0.05)

        assert captured_prompt == "Describe this image and assist with any requests"

    async def test_handle_photo_document(
        self,
        bot: VoiceAgentBot,
        mock_telegram_photo_context: MagicMock,
    ) -> None:
        """Test image sent as document."""
        update = MagicMock()
        update.effective_chat.id = 123
        update.message.photo = []
        update.message.document.file_id = "doc-image-id"
        update.message.document.mime_type = "image/png"
        update.message.caption = "Check this screenshot"
        update.message.reply_text = AsyncMock()

        captured_media_type = None

        async def mock_send_prompt(
            chat_id: int, prompt: str, **kwargs: object
        ) -> None:
            nonlocal captured_media_type
            images = kwargs.get("images")
            if images:
                captured_media_type = images[0].media_type
            yield "Screenshot analysis"  # type: ignore[misc]

        with patch.object(bot.session_manager, "send_prompt", mock_send_prompt):
            await bot.handle_photo(update, mock_telegram_photo_context)
            await asyncio.sleep(0.05)

        mock_telegram_photo_context.bot.get_file.assert_called_once_with("doc-image-id")
        assert captured_media_type == "image/png"

    async def test_handle_photo_not_allowed(
        self,
        bot: VoiceAgentBot,
        mock_telegram_photo_update: MagicMock,
        mock_telegram_photo_context: MagicMock,
    ) -> None:
        """Test photo from non-allowed chat is rejected."""
        mock_telegram_photo_update.effective_chat.id = 999

        await bot.handle_photo(
            mock_telegram_photo_update, mock_telegram_photo_context
        )

        mock_telegram_photo_context.bot.get_file.assert_not_called()
        mock_telegram_photo_update.message.reply_text.assert_not_called()
