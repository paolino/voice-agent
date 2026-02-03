"""Telegram bot for voice-controlled Claude Code.

Handles voice messages and routes them to Claude sessions.
"""

import asyncio
import contextlib
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
from voice_agent.telegram_format import convert_markdown_to_telegram
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
        self.storage = SessionStorage(path=settings.session_storage_path)
        self.session_manager = SessionManager(
            default_cwd=settings.default_cwd,
            permission_timeout=settings.permission_timeout,
            storage=self.storage,
        )
        self.allowed_chat_ids = settings.get_allowed_chat_ids()
        self._prompt_locks: dict[int, asyncio.Lock] = {}
        self._active_tasks: dict[int, asyncio.Task[None]] = {}
        self._cancel_flags: dict[int, bool] = {}
        self._pending_renames: dict[int, str] = {}  # chat_id -> session name to rename

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
            "Voice Agent ready. Send a voice or text message.\n\n"
            "Commands:\n"
            "- 'status' to check session state\n"
            "- 'sessions' to manage multiple sessions\n"
            "- 'new session' to start fresh\n"
            "- 'continue' to resume previous session\n"
            "- 'restart' to clear everything and start fresh\n"
            "- 'yes/approve' or 'no/reject' for permission prompts\n"
            "- 'always approve' to sticky-approve similar tool calls\n"
            "- 'clear sticky' to reset sticky approvals\n"
            "- 'escape/stop task/abort' to cancel running task"
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

        # Check for pending rename
        if chat_id in self._pending_renames:
            old_name = self._pending_renames.pop(chat_id)
            new_name = text.strip()
            if self.session_manager.rename_session(chat_id, old_name, new_name):
                await update.message.reply_text(f"Renamed '{old_name}' → '{new_name}'")
            else:
                await update.message.reply_text(
                    f"Failed to rename. Name '{new_name}' may already exist."
                )
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
            logger.info(
                "Downloaded %d bytes of audio from chat %s", len(audio_bytes), chat_id
            )
        except Exception as e:
            logger.error("Failed to download voice: %s", e)
            await update.message.reply_text(f"Failed to download audio: {e}")
            return

        # Transcribe
        try:
            text = await transcribe(bytes(audio_bytes), self.settings.whisper_url)

            # Delete the voice message to keep chat clean
            await update.message.delete()

            # Echo transcription unless it's a skill invocation
            stripped = text.strip()
            if not stripped.startswith("/") and not stripped.lower().startswith("skill "):
                from html import escape

                tag = self._session_tag(chat_id)
                await update.message.chat.send_message(
                    f"{tag} <i>{escape(text)}</i>", parse_mode="HTML"
                )
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
        elif command.command_type == CommandType.STICKY_APPROVE:
            await self._handle_sticky_approve(chat_id, update)
        elif command.command_type == CommandType.CLEAR_STICKY:
            await self._handle_clear_sticky(chat_id, update)
        elif command.command_type == CommandType.STATUS:
            await self._handle_status(chat_id, update)
        elif command.command_type == CommandType.NEW_SESSION:
            await self._handle_new_session(chat_id, update)
        elif command.command_type == CommandType.CONTINUE_SESSION:
            await self._handle_continue_session(chat_id, update)
        elif command.command_type == CommandType.SWITCH_PROJECT:
            await self._handle_switch_project(chat_id, command.project, update)
        elif command.command_type == CommandType.CANCEL:
            await self._handle_cancel(chat_id, update)
        elif command.command_type == CommandType.LIST_APPROVALS:
            await self._handle_list_approvals(chat_id, update)
        elif command.command_type == CommandType.RESTART:
            await self._handle_restart(chat_id, update)
        elif command.command_type == CommandType.SESSIONS:
            await self._handle_sessions(chat_id, update)
        else:
            await self._handle_prompt(chat_id, command.text, update)

    async def _handle_approve(self, chat_id: int, update: Update) -> None:
        """Handle permission approval (silent - no feedback needed)."""
        session = self.session_manager.get(chat_id)
        if not session:
            await update.message.reply_text("No active session.")  # type: ignore
            return

        if not session.permission_handler.approve():
            await update.message.reply_text("No pending permission to approve.")  # type: ignore

    async def _handle_reject(self, chat_id: int, update: Update) -> None:
        """Handle permission rejection."""
        session = self.session_manager.get(chat_id)
        if not session:
            await update.message.reply_text("No active session.")  # type: ignore
            return

        # Get description before denying
        desc = session.permission_handler.get_pending_description()
        if session.permission_handler.deny("User rejected via voice"):
            from html import escape

            await update.message.reply_text(  # type: ignore
                f"❌ <b>Rejected:</b> {escape(desc or 'unknown')}", parse_mode="HTML"
            )
        else:
            await update.message.reply_text("No pending permission to reject.")  # type: ignore

    async def _handle_sticky_approve(self, chat_id: int, update: Update) -> None:
        """Handle sticky approval - approve and remember for similar calls."""
        session = self.session_manager.get(chat_id)
        if not session:
            await update.message.reply_text("No active session.")  # type: ignore
            return

        sticky = session.permission_handler.sticky_approve()
        if sticky:
            await update.message.reply_text(  # type: ignore
                f"Stickied: {sticky.describe()} auto-approved"
            )
        else:
            await update.message.reply_text("No pending permission to sticky approve.")  # type: ignore

    async def _handle_clear_sticky(self, chat_id: int, update: Update) -> None:
        """Handle clearing all sticky approvals."""
        session = self.session_manager.get(chat_id)
        if not session:
            await update.message.reply_text("No active session.")  # type: ignore
            return

        count = session.permission_handler.clear_sticky_approvals()
        if count > 0:
            await update.message.reply_text(f"Cleared {count} sticky approval(s).")  # type: ignore
        else:
            await update.message.reply_text("No sticky approvals to clear.")  # type: ignore

    async def _handle_list_approvals(self, chat_id: int, update: Update) -> None:
        """Handle listing all sticky approvals with revoke buttons."""
        session = self.session_manager.get(chat_id)
        if not session:
            await update.message.reply_text("No active session.")  # type: ignore
            return

        approvals = session.permission_handler.get_sticky_approvals()
        if not approvals:
            await update.message.reply_text("No auto-approvals configured.")  # type: ignore
            return

        # Build message with list of approvals
        lines = ["<b>Auto-approvals:</b>"]
        for i, approval in enumerate(approvals):
            lines.append(f"{i + 1}. {approval.describe()}")

        # Build keyboard with revoke buttons (max 4 per row)
        buttons = [
            InlineKeyboardButton(f"❌ {i + 1}", callback_data=f"revoke_{i}")
            for i in range(len(approvals))
        ]
        # Chunk into rows of 4
        rows = [buttons[i : i + 4] for i in range(0, len(buttons), 4)]
        rows.append([InlineKeyboardButton("🗑️ Revoke All", callback_data="revoke_all")])
        keyboard = InlineKeyboardMarkup(rows)

        await update.message.reply_text(  # type: ignore
            "\n".join(lines), reply_markup=keyboard, parse_mode="HTML"
        )

    async def approvals_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /approvals command.

        Args:
            update: Telegram update.
            context: Callback context.
        """
        if not update.effective_chat:
            return

        chat_id = update.effective_chat.id
        if not self.is_allowed(chat_id):
            return

        await self._handle_list_approvals(chat_id, update)

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

        # Handle session operations first (don't require existing session)
        if query.data == "session_new":
            await self._handle_session_new_callback(chat_id, query)
            return
        if query.data.startswith("session_switch_"):
            name = query.data[15:]
            await self._handle_session_switch_callback(chat_id, name, query)
            return
        if query.data.startswith("session_close_confirm_"):
            name = query.data[22:]
            await self._handle_session_close_confirm_callback(chat_id, name, query)
            return
        if query.data.startswith("session_close_cancel_"):
            await query.delete_message()
            return
        if query.data.startswith("session_close_"):
            name = query.data[14:]
            await self._handle_session_close_callback(chat_id, name, query)
            return
        if query.data.startswith("session_rename_"):
            name = query.data[15:]
            await self._handle_session_rename_callback(chat_id, name, query)
            return

        session = self.session_manager.get(chat_id)
        if not session:
            await query.edit_message_text("No active session.")
            return

        if query.data == "approve":
            if session.permission_handler.approve():
                await query.delete_message()
            else:
                await query.edit_message_text("No pending permission.")
        elif query.data == "sticky_approve":
            sticky = session.permission_handler.sticky_approve()
            if sticky:
                await query.edit_message_text(
                    f"Stickied: {sticky.describe()} auto-approved"
                )
            else:
                await query.edit_message_text("No pending permission.")
        elif query.data == "reject":
            # Get description before denying (deny clears pending)
            desc = session.permission_handler.get_pending_description()
            if session.permission_handler.deny("User rejected via button"):
                from html import escape

                await query.edit_message_text(
                    f"❌ <b>Rejected:</b> {escape(desc or 'unknown')}",
                    parse_mode="HTML",
                )
            else:
                await query.edit_message_text("No pending permission.")
        elif query.data == "cancel":
            task = self._active_tasks.get(chat_id)
            if task and not task.done():
                self._cancel_flags[chat_id] = True
                task.cancel()
                # Don't edit message here - let run_prompt() handle cleanup
                # to avoid race condition with the finally block
            else:
                await query.edit_message_text("No running task to cancel.")
        elif query.data == "revoke_all":
            count = session.permission_handler.clear_sticky_approvals()
            if count > 0:
                await query.edit_message_text(f"Revoked all {count} auto-approval(s).")
            else:
                await query.edit_message_text("No auto-approvals to revoke.")
        elif query.data.startswith("revoke_"):
            index_str = query.data[7:]  # Remove "revoke_" prefix
            try:
                index = int(index_str)
                removed = session.permission_handler.remove_sticky_approval(index)
                if removed:
                    await query.edit_message_text(f"Revoked: {removed.describe()}")
                else:
                    await query.edit_message_text("Invalid approval index.")
            except ValueError:
                await query.edit_message_text("Invalid revoke command.")
        elif query.data == "confirm_restart":
            msg = await self._do_restart(chat_id)
            await query.edit_message_text(msg)
        elif query.data == "cancel_restart":
            await query.edit_message_text("Restart cancelled.")

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
            projects = ", ".join(self.settings.projects.keys())
            await update.message.reply_text(  # type: ignore
                f"Unknown project. Available: {projects}"
            )
            return

        cwd = self.settings.projects[project]
        self.session_manager.set_cwd(chat_id, cwd)
        await update.message.reply_text(f"Switched to {project} ({cwd})")  # type: ignore

    async def _handle_cancel(self, chat_id: int, update: Update) -> None:
        """Handle cancel/escape request to stop running task."""
        task = self._active_tasks.get(chat_id)
        if task and not task.done():
            self._cancel_flags[chat_id] = True
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            self._active_tasks.pop(chat_id, None)
            self._cancel_flags.pop(chat_id, None)
            await update.message.reply_text("⏹️ Task cancelled.")  # type: ignore
        else:
            await update.message.reply_text("No running task to cancel.")  # type: ignore

    async def _handle_restart(self, chat_id: int, update: Update) -> None:
        """Handle restart request - show confirmation dialog."""
        session = self.session_manager.get(chat_id)
        sticky_count = (
            len(session.permission_handler.get_sticky_approvals()) if session else 0
        )

        # Build confirmation message
        msg = "Are you sure you want to restart?"
        if sticky_count > 0:
            msg += f"\n\nThis will clear {sticky_count} auto-approval(s)."

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Yes, restart", callback_data="confirm_restart"
                    ),
                    InlineKeyboardButton("Cancel", callback_data="cancel_restart"),
                ]
            ]
        )
        await update.message.reply_text(msg, reply_markup=keyboard)  # type: ignore

    async def _do_restart(self, chat_id: int) -> str:
        """Actually perform the restart. Returns status message."""
        # Cancel any running task first
        task = self._active_tasks.get(chat_id)
        if task and not task.done():
            self._cancel_flags[chat_id] = True
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            self._active_tasks.pop(chat_id, None)
            self._cancel_flags.pop(chat_id, None)

        # Clear sticky approvals from existing session
        session = self.session_manager.get(chat_id)
        sticky_count = 0
        if session:
            sticky_count = session.permission_handler.clear_sticky_approvals()

        # Create fresh session (use async to properly close SDK client)
        await self.session_manager.create_new_async(chat_id)

        # Build status message
        parts = ["🔄 Restarted."]
        if sticky_count > 0:
            parts.append(f"Cleared {sticky_count} auto-approval(s).")
        parts.append("Fresh session started.")
        return " ".join(parts)

    async def _handle_sessions(self, chat_id: int, update: Update) -> None:
        """Handle sessions dialog request."""
        await self._show_sessions_dialog(chat_id, update)

    async def _show_sessions_dialog(self, chat_id: int, update: Update) -> None:
        """Show the sessions dialog with interactive buttons."""
        sessions = self.session_manager.list_sessions(chat_id)

        if not sessions:
            # No sessions yet, create main and show dialog
            self.session_manager.get_or_create(chat_id)
            sessions = self.session_manager.list_sessions(chat_id)

        # Build session list with fruit indicators
        lines = ["📂 <b>Sessions</b>\n"]
        fruits = self._SESSION_FRUITS
        for i, s in enumerate(sessions):
            fruit = fruits[i % len(fruits)]
            active = " ←" if s.is_active else ""
            cwd_short = s.cwd.split("/")[-1] or s.cwd
            lines.append(f"{fruit} {s.name}{active} · {s.message_count} msgs · {cwd_short}")

        # Build keyboard
        rows: list[list[InlineKeyboardButton]] = []

        # Switch buttons row
        switch_buttons = [
            InlineKeyboardButton(
                f"{fruits[i % len(fruits)]} {s.name}",
                callback_data=f"session_switch_{s.name}",
            )
            for i, s in enumerate(sessions)
        ]
        # Chunk switch buttons into rows of 2
        for i in range(0, len(switch_buttons), 2):
            rows.append(switch_buttons[i : i + 2])

        # New session button
        rows.append(
            [InlineKeyboardButton("+ New Session", callback_data="session_new")]
        )

        # Rename buttons row
        rename_buttons = [
            InlineKeyboardButton(
                f"✏️ {fruits[i % len(fruits)]}", callback_data=f"session_rename_{s.name}"
            )
            for i, s in enumerate(sessions)
        ]
        for i in range(0, len(rename_buttons), 2):
            rows.append(rename_buttons[i : i + 2])

        # Close buttons row
        close_buttons = [
            InlineKeyboardButton(
                f"✕ {fruits[i % len(fruits)]}", callback_data=f"session_close_{s.name}"
            )
            for i, s in enumerate(sessions)
        ]
        for i in range(0, len(close_buttons), 2):
            rows.append(close_buttons[i : i + 2])

        keyboard = InlineKeyboardMarkup(rows)

        await update.message.reply_text(  # type: ignore
            "\n".join(lines), reply_markup=keyboard, parse_mode="HTML"
        )

    async def sessions_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /sessions command.

        Args:
            update: Telegram update.
            context: Callback context.
        """
        if not update.effective_chat:
            return

        chat_id = update.effective_chat.id
        if not self.is_allowed(chat_id):
            return

        await self._handle_sessions(chat_id, update)

    async def _handle_session_new_callback(self, chat_id: int, query: Any) -> None:
        """Handle new session button click."""
        name = self.session_manager.generate_session_name(chat_id)
        self.session_manager.create_new(chat_id, name=name)
        fruit = self._session_tag(chat_id)
        await query.edit_message_text(f"{fruit} {name}")

    async def _handle_session_switch_callback(
        self, chat_id: int, name: str, query: Any
    ) -> None:
        """Handle session switch button click."""
        session = self.session_manager.switch_session(chat_id, name)
        if session:
            fruit = self._session_tag(chat_id)
            await query.edit_message_text(f"{fruit} {name}")
        else:
            await query.edit_message_text(f"Session '{name}' not found.")

    async def _handle_session_close_callback(
        self, chat_id: int, name: str, query: Any
    ) -> None:
        """Handle session close button click - show confirmation."""
        sessions = self.session_manager.list_sessions(chat_id)
        session_info = next((s for s in sessions if s.name == name), None)

        if not session_info:
            await query.edit_message_text(f"Session '{name}' not found.")
            return

        msg = f"Close session '{name}'?"
        if session_info.message_count > 0:
            msg += f"\n\nThis session has {session_info.message_count} message(s)."

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Yes, close", callback_data=f"session_close_confirm_{name}"
                    ),
                    InlineKeyboardButton(
                        "Cancel", callback_data=f"session_close_cancel_{name}"
                    ),
                ]
            ]
        )
        await query.edit_message_text(msg, reply_markup=keyboard)

    async def _handle_session_close_confirm_callback(
        self, chat_id: int, name: str, query: Any
    ) -> None:
        """Handle session close confirmation."""
        closed = await self.session_manager.close_session_async(chat_id, name)
        if closed:
            await query.delete_message()
        else:
            await query.edit_message_text(f"Session '{name}' not found.")

    async def _handle_session_rename_callback(
        self, chat_id: int, name: str, query: Any
    ) -> None:
        """Handle session rename button click - prompt for new name."""
        self._pending_renames[chat_id] = name
        await query.edit_message_text(f"Send new name for session '{name}':")

    async def restart_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /restart command.

        Args:
            update: Telegram update.
            context: Callback context.
        """
        if not update.effective_chat:
            return

        chat_id = update.effective_chat.id
        if not self.is_allowed(chat_id):
            return

        await self._handle_restart(chat_id, update)

    def _get_prompt_lock(self, chat_id: int) -> asyncio.Lock:
        """Get or create a lock for serializing prompts per chat."""
        if chat_id not in self._prompt_locks:
            self._prompt_locks[chat_id] = asyncio.Lock()
        return self._prompt_locks[chat_id]

    async def _send_formatted(
        self, update: Update, text: str, chat_id: int | None = None
    ) -> None:
        """Send a message with Telegram MarkdownV2 formatting.

        Falls back to plain text if formatting fails.

        Args:
            update: Telegram update for replying.
            text: Text to send (may contain Markdown).
            chat_id: Optional chat ID for session tag.
        """
        if chat_id:
            tag = self._session_tag(chat_id)
            text = f"{tag} {text}"
        try:
            formatted = convert_markdown_to_telegram(text)
            await update.message.reply_text(  # type: ignore
                formatted, parse_mode="MarkdownV2"
            )
        except Exception as e:
            # Fall back to plain text if formatting fails
            logger.debug("Markdown formatting failed, falling back to plain: %s", e)
            await update.message.reply_text(text)  # type: ignore

    _SESSION_FRUITS = ["🍎", "🍊", "🍋", "🍇", "🍉", "🍓", "🍑", "🍒", "🥝", "🍍"]

    def _session_tag(self, chat_id: int) -> str:
        """Get session indicator tag for messages."""
        sessions = self.session_manager.list_sessions(chat_id)
        active = self.session_manager.get_active_session_name(chat_id)
        for i, s in enumerate(sessions):
            if s.name == active:
                return self._SESSION_FRUITS[i % len(self._SESSION_FRUITS)]
        return self._SESSION_FRUITS[0]

    async def unknown_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Forward unknown /commands to Claude as skill invocations.

        Args:
            update: Telegram update.
            context: Callback context.
        """
        if not update.effective_chat or not update.message:
            return

        chat_id = update.effective_chat.id
        if not self.is_allowed(chat_id):
            return

        text = update.message.text
        if not text:
            return

        # Delete the command message to keep chat clean
        await update.message.delete()

        await self._handle_prompt(chat_id, text, update)

    async def _handle_prompt(self, chat_id: int, text: str, update: Update) -> None:
        """Handle a prompt to send to Claude."""
        tag = self._session_tag(chat_id)

        # Set up notification callback for this chat
        async def notify_permission(tool_name: str, input_data: dict[str, Any]) -> None:
            desc = f"{tag} Claude wants to use {tool_name}"
            if tool_name == "Bash":
                cmd = input_data.get("command", "unknown")
                desc = f"{tag} Run: {cmd}"
            elif tool_name in ("Write", "Edit"):
                path = input_data.get("file_path", "unknown")
                desc = f"{tag} Modify: {path}"
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Approve", callback_data="approve"),
                        InlineKeyboardButton("Always", callback_data="sticky_approve"),
                        InlineKeyboardButton("Reject", callback_data="reject"),
                    ]
                ]
            )
            await update.message.reply_text(desc, reply_markup=keyboard)  # type: ignore

        self.session_manager.set_notify_callback(chat_id, notify_permission)

        lock = self._get_prompt_lock(chat_id)

        # Run prompt in background task so bot can still receive messages
        async def run_prompt() -> None:
            # Notify if we're waiting for another prompt to finish
            if lock.locked():
                await update.message.reply_text(
                    f"{tag} (Queued, waiting for previous request...)"
                )  # type: ignore
            async with lock:
                logger.info("Processing prompt for chat %s: %s", chat_id, text[:50])
                self._cancel_flags[chat_id] = False

                # Send "working" message with Stop button
                stop_keyboard = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🛑 Stop", callback_data="cancel")]]
                )
                working_msg = await update.message.reply_text(  # type: ignore
                    f"{tag} ⏳ Working...", reply_markup=stop_keyboard
                )

                response_buffer: list[str] = []
                try:
                    async for chunk in self.session_manager.send_prompt(chat_id, text):
                        # Check if cancelled
                        if self._cancel_flags.get(chat_id, False):
                            logger.info("Task cancelled for chat %s", chat_id)
                            break
                        response_buffer.append(chunk)

                        # Send in batches to avoid too many messages
                        if len(response_buffer) >= 5:
                            await self._send_formatted(
                                update, "\n".join(response_buffer), chat_id
                            )
                            response_buffer = []

                    # Send remaining
                    if response_buffer and not self._cancel_flags.get(chat_id, False):
                        await self._send_formatted(
                            update, "\n".join(response_buffer), chat_id
                        )
                except asyncio.CancelledError:
                    logger.info("Task cancelled for chat %s", chat_id)
                except Exception as e:
                    logger.exception("Error in background prompt for chat %s", chat_id)
                    await update.message.reply_text(f"Error: {e}")  # type: ignore
                finally:
                    was_cancelled = self._cancel_flags.get(chat_id, False)
                    self._active_tasks.pop(chat_id, None)
                    self._cancel_flags.pop(chat_id, None)
                    # Update or remove the "Working..." message
                    with contextlib.suppress(Exception):
                        if was_cancelled:
                            await working_msg.edit_text("⏹️ Task cancelled.")
                        else:
                            await working_msg.delete()

        task = asyncio.create_task(run_prompt())
        self._active_tasks[chat_id] = task

    def build_application(self) -> Application:  # type: ignore
        """Build the Telegram application.

        Returns:
            Configured Application instance.
        """
        app = Application.builder().token(self.settings.telegram_bot_token).build()

        # Add handlers
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("status", self.status_command))
        app.add_handler(CommandHandler("restart", self.restart_command))
        app.add_handler(CommandHandler("approvals", self.approvals_command))
        app.add_handler(CommandHandler("sessions", self.sessions_command))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        app.add_handler(MessageHandler(filters.VOICE, self.handle_voice))
        app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text)
        )
        # Catch-all for unrecognized /commands - forward to Claude for skill invocation
        app.add_handler(MessageHandler(filters.COMMAND, self.unknown_command))

        return app

    def run(self) -> None:
        """Run the bot with polling."""
        logger.info("Starting Voice Agent bot...")
        app = self.build_application()
        app.run_polling(allowed_updates=Update.ALL_TYPES)
