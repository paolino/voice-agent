"""Session management for Claude Code SDK.

Manages Claude SDK client instances and their lifecycle.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from voice_agent.sessions.permissions import PermissionHandler

if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeSDKClient
    from voice_agent.sessions.storage import SessionStorage, StoredSession

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """A Claude Code session.

    Attributes:
        chat_id: Telegram chat ID this session belongs to.
        cwd: Working directory for the session.
        created_at: When the session was created.
        message_count: Number of messages exchanged.
        permission_handler: Handler for permission requests.
        sdk_client: Persistent ClaudeSDKClient instance.
        claude_session_id: Claude CLI session ID for resume.
    """

    chat_id: int
    cwd: str
    created_at: datetime = field(default_factory=datetime.now)
    message_count: int = 0
    permission_handler: PermissionHandler = field(default_factory=PermissionHandler)
    sdk_client: "ClaudeSDKClient | None" = None
    claude_session_id: str | None = None

    def get_status(self) -> str:
        """Get a human-readable status of this session.

        Returns:
            Status string.
        """
        age = datetime.now() - self.created_at
        hours, remainder = divmod(int(age.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)

        status_parts = [
            f"Working directory: {self.cwd}",
            f"Messages: {self.message_count}",
            f"Age: {hours}h {minutes}m",
        ]

        if self.permission_handler.has_pending():
            desc = self.permission_handler.get_pending_description()
            status_parts.append(f"Pending approval: {desc}")

        return "\n".join(status_parts)


class SessionManager:
    """Manages Claude Code sessions per chat.

    Attributes:
        sessions: Mapping of chat_id to Session.
        default_cwd: Default working directory for new sessions.
        permission_timeout: Timeout for permission requests.
        storage: Optional persistent storage for sessions.
    """

    def __init__(
        self,
        default_cwd: str = "/code",
        permission_timeout: int = 300,
        storage: "SessionStorage | None" = None,
    ) -> None:
        """Initialize the session manager.

        Args:
            default_cwd: Default working directory for new sessions.
            permission_timeout: Timeout in seconds for permission requests.
            storage: Optional storage for session persistence.
        """
        self.sessions: dict[int, Session] = {}
        self.default_cwd = default_cwd
        self.permission_timeout = permission_timeout
        self.storage = storage
        self._notify_callbacks: dict[int, Any] = {}
        self._restore_sessions()

    def _restore_sessions(self) -> None:
        """Restore sessions from storage."""
        if not self.storage:
            return

        for stored in self.storage.list_all():
            # Parse created_at from ISO format
            try:
                created_at = datetime.fromisoformat(stored.created_at)
            except ValueError:
                created_at = datetime.now()

            session = Session(
                chat_id=stored.chat_id,
                cwd=stored.cwd,
                created_at=created_at,
                message_count=stored.message_count,
                claude_session_id=stored.claude_session_id,
                permission_handler=PermissionHandler(
                    timeout=self.permission_timeout,
                    notify_callback=self._notify_callbacks.get(stored.chat_id),
                ),
            )
            self.sessions[stored.chat_id] = session

    def _persist_session(self, session: Session) -> None:
        """Persist a session to storage."""
        if not self.storage:
            return

        from voice_agent.sessions.storage import StoredSession

        stored = StoredSession(
            chat_id=session.chat_id,
            cwd=session.cwd,
            created_at=session.created_at.isoformat(),
            message_count=session.message_count,
            claude_session_id=session.claude_session_id,
        )
        self.storage.save(stored)

    def set_notify_callback(
        self, chat_id: int, callback: Any
    ) -> None:
        """Set the notification callback for a chat.

        Args:
            chat_id: Telegram chat ID.
            callback: Async function to call for notifications.
        """
        self._notify_callbacks[chat_id] = callback

    def get_or_create(self, chat_id: int, cwd: str | None = None) -> Session:
        """Get existing session or create new one.

        Args:
            chat_id: Telegram chat ID.
            cwd: Working directory (uses default if not specified).

        Returns:
            The session for this chat.
        """
        if chat_id not in self.sessions:
            effective_cwd = cwd or self.default_cwd
            session = Session(
                chat_id=chat_id,
                cwd=effective_cwd,
                permission_handler=PermissionHandler(
                    timeout=self.permission_timeout,
                    notify_callback=self._notify_callbacks.get(chat_id),
                ),
            )
            self.sessions[chat_id] = session
            self._persist_session(session)
        return self.sessions[chat_id]

    async def create_new_async(self, chat_id: int, cwd: str | None = None) -> Session:
        """Create a new session, replacing any existing one.

        Args:
            chat_id: Telegram chat ID.
            cwd: Working directory.

        Returns:
            The new session.
        """
        # Clean up old session if exists
        if chat_id in self.sessions:
            old_session = self.sessions[chat_id]
            await self._close_client(old_session)

        effective_cwd = cwd or self.default_cwd
        session = Session(
            chat_id=chat_id,
            cwd=effective_cwd,
            permission_handler=PermissionHandler(
                timeout=self.permission_timeout,
                notify_callback=self._notify_callbacks.get(chat_id),
            ),
        )
        self.sessions[chat_id] = session
        self._persist_session(session)
        return session

    def create_new(self, chat_id: int, cwd: str | None = None) -> Session:
        """Create a new session synchronously (closes client in background).

        Args:
            chat_id: Telegram chat ID.
            cwd: Working directory.

        Returns:
            The new session.
        """
        # Clean up old session if exists
        if chat_id in self.sessions:
            old_session = self.sessions[chat_id]
            if old_session.sdk_client is not None:
                # Schedule async cleanup
                asyncio.create_task(self._close_client(old_session))

        effective_cwd = cwd or self.default_cwd
        session = Session(
            chat_id=chat_id,
            cwd=effective_cwd,
            permission_handler=PermissionHandler(
                timeout=self.permission_timeout,
                notify_callback=self._notify_callbacks.get(chat_id),
            ),
        )
        self.sessions[chat_id] = session
        self._persist_session(session)
        return session

    def get(self, chat_id: int) -> Session | None:
        """Get session for a chat if it exists.

        Args:
            chat_id: Telegram chat ID.

        Returns:
            Session or None.
        """
        return self.sessions.get(chat_id)

    def set_cwd(self, chat_id: int, cwd: str) -> Session:
        """Set the working directory for a session.

        Args:
            chat_id: Telegram chat ID.
            cwd: New working directory.

        Returns:
            The updated session.
        """
        session = self.get_or_create(chat_id)
        session.cwd = cwd
        self._persist_session(session)
        return session

    async def _get_or_create_client(self, session: Session) -> "ClaudeSDKClient":
        """Get or create a ClaudeSDKClient for the session.

        Args:
            session: The session to get/create client for.

        Returns:
            ClaudeSDKClient instance.
        """
        if session.sdk_client is None:
            import shutil

            from claude_agent_sdk import (
                ClaudeAgentOptions,
                ClaudeSDKClient,
                PermissionResultAllow,
                PermissionResultDeny,
                ToolPermissionContext,
            )

            # Use system Claude CLI (2.0+) instead of bundled SDK version (1.3.5)
            # The SDK's bundled CLI is too old and lacks required features
            cli_path = shutil.which("claude")

            async def permission_callback(
                tool_name: str,
                input_data: dict[str, Any],
                context: ToolPermissionContext,
            ) -> PermissionResultAllow | PermissionResultDeny:
                """Handle tool permission requests via the session's permission handler."""
                approved, deny_message = await session.permission_handler.request_permission(
                    tool_name, input_data
                )
                if approved:
                    return PermissionResultAllow()
                return PermissionResultDeny(message=deny_message or "Permission denied")

            options = ClaudeAgentOptions(
                cwd=session.cwd,
                can_use_tool=permission_callback,
                cli_path=cli_path,
            )
            session.sdk_client = ClaudeSDKClient(options=options)
            await session.sdk_client.__aenter__()
            logger.info(
                "Created new SDK client for chat %s (CLI: %s)", session.chat_id, cli_path
            )

        return session.sdk_client

    async def _close_client(self, session: Session) -> None:
        """Close the SDK client for a session.

        Args:
            session: The session whose client to close.
        """
        if session.sdk_client is not None:
            try:
                await session.sdk_client.__aexit__(None, None, None)
            except Exception as e:
                logger.warning("Error closing SDK client: %s", e)
            session.sdk_client = None

    async def send_prompt(
        self, chat_id: int, prompt: str, resume: bool = True
    ) -> AsyncIterator[str]:
        """Send a prompt to the session and stream responses.

        Uses ClaudeSDKClient for persistent sessions - no token reload.

        Args:
            chat_id: Telegram chat ID.
            prompt: The prompt to send.
            resume: Whether to resume existing session if available.

        Yields:
            Response chunks from Claude.
        """
        from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

        session = self.get_or_create(chat_id)
        session.message_count += 1

        try:
            client = await self._get_or_create_client(session)
            await client.query(prompt)

            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            yield block.text
                elif isinstance(msg, ResultMessage):
                    if msg.total_cost_usd:
                        logger.info(
                            "Chat %s message cost: $%.4f",
                            chat_id,
                            msg.total_cost_usd,
                        )

            # Persist updated session
            self._persist_session(session)

        except ImportError:
            yield "Error: claude-agent-sdk not installed. Install with: pip install claude-agent-sdk"
        except Exception as e:
            logger.exception("Error in send_prompt for chat %s", chat_id)
            yield f"Error: {e}"
            # Close client on error so it can be recreated
            await self._close_client(session)

    def get_status(self, chat_id: int) -> str | None:
        """Get status of a session.

        Args:
            chat_id: Telegram chat ID.

        Returns:
            Status string or None if no session.
        """
        session = self.get(chat_id)
        if not session:
            return None
        return session.get_status()

    async def delete_session_async(self, chat_id: int) -> bool:
        """Delete a session asynchronously.

        Args:
            chat_id: Telegram chat ID.

        Returns:
            True if session was deleted, False if not found.
        """
        if chat_id not in self.sessions:
            return False

        session = self.sessions[chat_id]
        await self._close_client(session)

        del self.sessions[chat_id]

        if self.storage:
            self.storage.delete(chat_id)

        return True

    def delete_session(self, chat_id: int) -> bool:
        """Delete a session synchronously.

        Args:
            chat_id: Telegram chat ID.

        Returns:
            True if session was deleted, False if not found.
        """
        if chat_id not in self.sessions:
            return False

        session = self.sessions[chat_id]
        if session.sdk_client is not None:
            asyncio.create_task(self._close_client(session))

        del self.sessions[chat_id]

        if self.storage:
            self.storage.delete(chat_id)

        return True

    def set_claude_session_id(self, chat_id: int, session_id: str | None) -> None:
        """Set the Claude session ID for resume capability.

        Args:
            chat_id: Telegram chat ID.
            session_id: Claude CLI session ID or None to clear.
        """
        session = self.get(chat_id)
        if session:
            session.claude_session_id = session_id
            self._persist_session(session)

    def has_resumable_session(self, chat_id: int) -> bool:
        """Check if a chat has a resumable Claude session.

        Args:
            chat_id: Telegram chat ID.

        Returns:
            True if there's a session with a Claude session ID.
        """
        session = self.get(chat_id)
        return session is not None and session.claude_session_id is not None
