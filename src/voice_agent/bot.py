"""Telegram bot for voice-controlled Claude Code.

Handles voice messages and routes them to Claude sessions.
"""

import logging
from typing import Any

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from voice_agent.config import Settings
from voice_agent.router import CommandType, parse_command
from voice_agent.sessions import SessionManager
from voice_agent.transcribe import TranscriptionError, transcribe

logger = logging.getLogger(__name__)


class VoiceAgentBot:
    """Telegram bot for voice control of Claude Code.

    Attributes:
        settings: Application settings.
        session_manager: Manages Claude sessions.
        allowed_chat_ids: Set of chat IDs allowed to use the bot.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the bot.

        Args:
            settings: Application settings.
        """
        self.settings = settings
        self.session_manager = SessionManager(
            default_cwd=settings.default_cwd,
            permission_timeout=settings.permission_timeout,
        )
        self.allowed_chat_ids = settings.get_allowed_chat_ids()

    def is_allowed(self, chat_id: int) -> bool:
        """Check if a chat ID is allowed to use the bot.

        Args:
            chat_id: Telegram chat ID.

        Returns:
            True if allowed (or if no whitelist configured).
        """
        if not self.allowed_chat_ids:
            return True
        return chat_id in self.allowed_chat_ids

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /start command.

        Args:
            update: Telegram update.
            context: Callback context.
        """
        if not update.effective_chat:
            return

        chat_id = update.effective_chat.id
        if not self.is_allowed(chat_id):
            return

        await update.message.reply_text(  # type: ignore
            "Voice Agent ready. Send a voice message to interact with Claude Code.\n\n"
            "Commands:\n"
            "- Say 'status' to check session state\n"
            "- Say 'new session' to start fresh\n"
            "- Say 'yes/approve' or 'no/reject' for permission prompts"
        )

    async def status_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /status command.

        Args:
            update: Telegram update.
            context: Callback context.
        """
        if not update.effective_chat:
            return

        chat_id = update.effective_chat.id
        if not self.is_allowed(chat_id):
            return

        status = self.session_manager.get_status(chat_id)
        if status:
            await update.message.reply_text(status)  # type: ignore
        else:
            await update.message.reply_text("No active session.")  # type: ignore

    async def handle_voice(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle incoming voice messages.

        Args:
            update: Telegram update.
            context: Callback context.
        """
        if not update.effective_chat or not update.message:
            return

        chat_id = update.effective_chat.id
        if not self.is_allowed(chat_id):
            logger.debug("Ignoring voice from non-allowed chat %s", chat_id)
            return

        voice = update.message.voice
        if not voice:
            return

        # Download audio
        try:
            file = await context.bot.get_file(voice.file_id)
            audio_bytes = await file.download_as_bytearray()
            logger.info("Downloaded %d bytes of audio from chat %s", len(audio_bytes), chat_id)
        except Exception as e:
            logger.error("Failed to download voice: %s", e)
            await update.message.reply_text(f"Failed to download audio: {e}")
            return

        # Transcribe
        try:
            text = await transcribe(bytes(audio_bytes), self.settings.whisper_url)
            await update.message.reply_text(f"Heard: {text}")
        except TranscriptionError as e:
            logger.error("Transcription failed: %s", e)
            await update.message.reply_text(f"Transcription failed: {e}")
            return

        # Route command
        await self._handle_transcription(chat_id, text, update)

    async def _handle_transcription(
        self, chat_id: int, text: str, update: Update
    ) -> None:
        """Handle a transcribed voice message.

        Args:
            chat_id: Telegram chat ID.
            text: Transcribed text.
            update: Telegram update for replying.
        """
        command = parse_command(text, self.settings.projects)

        if command.command_type == CommandType.APPROVE:
            await self._handle_approve(chat_id, update)
        elif command.command_type == CommandType.REJECT:
            await self._handle_reject(chat_id, update)
        elif command.command_type == CommandType.STATUS:
            await self._handle_status(chat_id, update)
        elif command.command_type == CommandType.NEW_SESSION:
            await self._handle_new_session(chat_id, update)
        elif command.command_type == CommandType.SWITCH_PROJECT:
            await self._handle_switch_project(chat_id, command.project, update)
        else:
            await self._handle_prompt(chat_id, command.text, update)

    async def _handle_approve(self, chat_id: int, update: Update) -> None:
        """Handle permission approval."""
        session = self.session_manager.get(chat_id)
        if not session:
            await update.message.reply_text("No active session.")  # type: ignore
            return

        if session.permission_handler.approve():
            await update.message.reply_text("Approved.")  # type: ignore
        else:
            await update.message.reply_text("No pending permission to approve.")  # type: ignore

    async def _handle_reject(self, chat_id: int, update: Update) -> None:
        """Handle permission rejection."""
        session = self.session_manager.get(chat_id)
        if not session:
            await update.message.reply_text("No active session.")  # type: ignore
            return

        if session.permission_handler.deny("User rejected via voice"):
            await update.message.reply_text("Rejected.")  # type: ignore
        else:
            await update.message.reply_text("No pending permission to reject.")  # type: ignore

    async def _handle_status(self, chat_id: int, update: Update) -> None:
        """Handle status request."""
        status = self.session_manager.get_status(chat_id)
        if status:
            await update.message.reply_text(status)  # type: ignore
        else:
            await update.message.reply_text("No active session.")  # type: ignore

    async def _handle_new_session(self, chat_id: int, update: Update) -> None:
        """Handle new session request."""
        self.session_manager.create_new(chat_id)
        await update.message.reply_text("Started new session.")  # type: ignore

    async def _handle_switch_project(
        self, chat_id: int, project: str | None, update: Update
    ) -> None:
        """Handle project switch request."""
        if not project or project not in self.settings.projects:
            await update.message.reply_text(  # type: ignore
                f"Unknown project. Available: {', '.join(self.settings.projects.keys())}"
            )
            return

        cwd = self.settings.projects[project]
        self.session_manager.set_cwd(chat_id, cwd)
        await update.message.reply_text(f"Switched to {project} ({cwd})")  # type: ignore

    async def _handle_prompt(self, chat_id: int, text: str, update: Update) -> None:
        """Handle a prompt to send to Claude."""
        # Set up notification callback for this chat
        async def notify_permission(tool_name: str, input_data: dict[str, Any]) -> None:
            desc = f"Claude wants to use {tool_name}"
            if tool_name == "Bash":
                desc = f"Claude wants to run: {input_data.get('command', 'unknown')}"
            elif tool_name in ("Write", "Edit"):
                desc = f"Claude wants to modify: {input_data.get('file_path', 'unknown')}"
            await update.message.reply_text(  # type: ignore
                f"{desc}\n\nSay 'approve' or 'reject'"
            )

        self.session_manager.set_notify_callback(chat_id, notify_permission)

        # Send prompt and stream responses
        response_buffer = []
        async for chunk in self.session_manager.send_prompt(chat_id, text):
            response_buffer.append(chunk)

            # Send in batches to avoid too many messages
            if len(response_buffer) >= 5:
                await update.message.reply_text("\n".join(response_buffer))  # type: ignore
                response_buffer = []

        # Send remaining
        if response_buffer:
            await update.message.reply_text("\n".join(response_buffer))  # type: ignore

    def build_application(self) -> Application:  # type: ignore
        """Build the Telegram application.

        Returns:
            Configured Application instance.
        """
        app = Application.builder().token(self.settings.telegram_bot_token).build()

        # Add handlers
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("status", self.status_command))
        app.add_handler(MessageHandler(filters.VOICE, self.handle_voice))

        return app

    def run(self) -> None:
        """Run the bot with polling."""
        logger.info("Starting Voice Agent bot...")
        app = self.build_application()
        app.run_polling(allowed_updates=Update.ALL_TYPES)
