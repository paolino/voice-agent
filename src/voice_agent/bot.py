"""Telegram bot for voice-controlled Claude Code.

Handles voice messages and routes them to Claude sessions.
"""

import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from voice_agent.config import Settings
from voice_agent.router import CommandType, parse_command
from voice_agent.sessions import SessionManager, SessionStorage
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
        import asyncio

        self.settings = settings
        self.storage = SessionStorage(path=settings.session_storage_path)
        self.session_manager = SessionManager(
            default_cwd=settings.default_cwd,
            permission_timeout=settings.permission_timeout,
            storage=self.storage,
        )
        self.allowed_chat_ids = settings.get_allowed_chat_ids()
        self._prompt_locks: dict[int, asyncio.Lock] = {}

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
            "Voice Agent ready. Send a voice or text message to interact with Claude Code.\n\n"
            "Commands:\n"
            "- 'status' to check session state\n"
            "- 'new session' to start fresh\n"
            "- 'continue' to resume previous session\n"
            "- 'yes/approve' or 'no/reject' for permission prompts"
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

    async def handle_text(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle incoming text messages.

        Args:
            update: Telegram update.
            context: Callback context.
        """
        if not update.effective_chat or not update.message:
            return

        chat_id = update.effective_chat.id
        if not self.is_allowed(chat_id):
            logger.debug("Ignoring text from non-allowed chat %s", chat_id)
            return

        text = update.message.text
        if not text:
            return

        logger.info("Received text from chat %s: %s", chat_id, text[:50])
        await self._handle_transcription(chat_id, text, update)

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
            from html import escape
            await update.message.reply_text(f"<i>{escape(text)}</i>", parse_mode="HTML")
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
        elif command.command_type == CommandType.CONTINUE_SESSION:
            await self._handle_continue_session(chat_id, update)
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

    async def handle_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle inline keyboard button presses."""
        query = update.callback_query
        if not query or not query.data:
            return

        await query.answer()

        chat_id = query.message.chat.id if query.message else None
        if not chat_id or not self.is_allowed(chat_id):
            return

        session = self.session_manager.get(chat_id)
        if not session:
            await query.edit_message_text("No active session.")
            return

        if query.data == "approve":
            if session.permission_handler.approve():
                await query.edit_message_text("Approved.")
            else:
                await query.edit_message_text("No pending permission.")
        elif query.data == "reject":
            if session.permission_handler.deny("User rejected via button"):
                await query.edit_message_text("Rejected.")
            else:
                await query.edit_message_text("No pending permission.")

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

    async def _handle_continue_session(self, chat_id: int, update: Update) -> None:
        """Handle continue/resume session request."""
        if self.session_manager.has_resumable_session(chat_id):
            session = self.session_manager.get(chat_id)
            await update.message.reply_text(  # type: ignore
                f"Resuming session in {session.cwd}\n"  # type: ignore
                f"Messages: {session.message_count}"  # type: ignore
            )
        else:
            # No resumable session, check if there's stored session data
            session = self.session_manager.get(chat_id)
            if session:
                await update.message.reply_text(  # type: ignore
                    f"Session active in {session.cwd}. No Claude session to resume.\n"
                    "Send a message to start interacting."
                )
            else:
                await update.message.reply_text(  # type: ignore
                    "No previous session to resume. Starting fresh."
                )
                self.session_manager.create_new(chat_id)

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

    def _get_prompt_lock(self, chat_id: int) -> "asyncio.Lock":
        """Get or create a lock for serializing prompts per chat."""
        import asyncio

        if chat_id not in self._prompt_locks:
            self._prompt_locks[chat_id] = asyncio.Lock()
        return self._prompt_locks[chat_id]

    async def _handle_prompt(self, chat_id: int, text: str, update: Update) -> None:
        """Handle a prompt to send to Claude."""
        import asyncio

        # Set up notification callback for this chat
        async def notify_permission(tool_name: str, input_data: dict[str, Any]) -> None:
            desc = f"Claude wants to use {tool_name}"
            if tool_name == "Bash":
                desc = f"Claude wants to run: {input_data.get('command', 'unknown')}"
            elif tool_name in ("Write", "Edit"):
                desc = f"Claude wants to modify: {input_data.get('file_path', 'unknown')}"
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Approve", callback_data="approve"),
                    InlineKeyboardButton("Reject", callback_data="reject"),
                ]
            ])
            await update.message.reply_text(desc, reply_markup=keyboard)  # type: ignore

        self.session_manager.set_notify_callback(chat_id, notify_permission)

        lock = self._get_prompt_lock(chat_id)

        # Run prompt in background task so bot can still receive messages
        async def run_prompt() -> None:
            # Notify if we're waiting for another prompt to finish
            if lock.locked():
                await update.message.reply_text("(Queued, waiting for previous request...)")  # type: ignore
            async with lock:
                logger.info("Processing prompt for chat %s: %s", chat_id, text[:50])
                response_buffer = []
                try:
                    async for chunk in self.session_manager.send_prompt(chat_id, text):
                        response_buffer.append(chunk)

                        # Send in batches to avoid too many messages
                        if len(response_buffer) >= 5:
                            await update.message.reply_text("\n".join(response_buffer))  # type: ignore
                            response_buffer = []

                    # Send remaining
                    if response_buffer:
                        await update.message.reply_text("\n".join(response_buffer))  # type: ignore
                except Exception as e:
                    logger.exception("Error in background prompt for chat %s", chat_id)
                    await update.message.reply_text(f"Error: {e}")  # type: ignore

        asyncio.create_task(run_prompt())

    def build_application(self) -> Application:  # type: ignore
        """Build the Telegram application.

        Returns:
            Configured Application instance.
        """
        app = Application.builder().token(self.settings.telegram_bot_token).build()

        # Add handlers
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("status", self.status_command))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        app.add_handler(MessageHandler(filters.VOICE, self.handle_voice))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

        return app

    def run(self) -> None:
        """Run the bot with polling."""
        logger.info("Starting Voice Agent bot...")
        app = self.build_application()
        app.run_polling(allowed_updates=Update.ALL_TYPES)
