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

    from voice_agent.sessions.storage import SessionStorage

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """A Claude Code session.

    Attributes:
        chat_id: Telegram chat ID this session belongs to.
        name: Session name within the chat.
        cwd: Working directory for the session.
        created_at: When the session was created.
        message_count: Number of messages exchanged.
        permission_handler: Handler for permission requests.
        sdk_client: Persistent ClaudeSDKClient instance.
        claude_session_id: Claude CLI session ID for resume.
    """

    chat_id: int
    name: str
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
            f"Session: {self.name}",
            f"Working directory: {self.cwd}",
            f"Messages: {self.message_count}",
            f"Age: {hours}h {minutes}m",
        ]

        if self.permission_handler.has_pending():
            desc = self.permission_handler.get_pending_description()
            status_parts.append(f"Pending approval: {desc}")

        sticky_approvals = self.permission_handler.get_sticky_approvals()
        if sticky_approvals:
            status_parts.append(f"Sticky approvals ({len(sticky_approvals)}):")
            for approval in sticky_approvals:
                status_parts.append(f"  - {approval.describe()}")

        return "\n".join(status_parts)


@dataclass
class SessionInfo:
    """Summary info for a session, used in listings.

    Attributes:
        name: Session name.
        message_count: Number of messages exchanged.
        cwd: Working directory.
        is_active: Whether this is the active session.
    """

    name: str
    message_count: int
    cwd: str
    is_active: bool


class SessionManager:
    """Manages Claude Code sessions per chat with multi-session support.

    Attributes:
        sessions: Mapping of chat_id to dict of session_name to Session.
        active_sessions: Mapping of chat_id to active session name.
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
        self.sessions: dict[int, dict[str, Session]] = {}
        self.active_sessions: dict[int, str] = {}
        self.default_cwd = default_cwd
        self.permission_timeout = permission_timeout
        self.storage = storage
        self._notify_callbacks: dict[int, Any] = {}
        self._restore_sessions()

    def _restore_sessions(self) -> None:
        """Restore sessions from storage."""
        if not self.storage:
            return

        for chat_id in self.storage.list_all_chats():
            state = self.storage.get_chat_state(chat_id)
            if not state:
                continue

            self.sessions[chat_id] = {}
            self.active_sessions[chat_id] = state.active_session

            for stored in state.sessions.values():
                try:
                    created_at = datetime.fromisoformat(stored.created_at)
                except ValueError:
                    created_at = datetime.now()

                session = Session(
                    chat_id=stored.chat_id,
                    name=stored.name,
                    cwd=stored.cwd,
                    created_at=created_at,
                    message_count=stored.message_count,
                    claude_session_id=stored.claude_session_id,
                    permission_handler=PermissionHandler(
                        timeout=self.permission_timeout,
                        notify_callback=self._notify_callbacks.get(stored.chat_id),
                    ),
                )
                self.sessions[chat_id][stored.name] = session

    def _persist_session(self, session: Session) -> None:
        """Persist a session to storage."""
        if not self.storage:
            return

        from voice_agent.sessions.storage import StoredSession

        stored = StoredSession(
            chat_id=session.chat_id,
            name=session.name,
            cwd=session.cwd,
            created_at=session.created_at.isoformat(),
            message_count=session.message_count,
            claude_session_id=session.claude_session_id,
        )
        self.storage.save(stored)

    def set_notify_callback(self, chat_id: int, callback: Any) -> None:
        """Set the notification callback for a chat.

        Args:
            chat_id: Telegram chat ID.
            callback: Async function to call for notifications.
        """
        self._notify_callbacks[chat_id] = callback
        # Also update existing session's permission handler
        if chat_id in self.sessions:
            for session in self.sessions[chat_id].values():
                session.permission_handler.notify_callback = callback

    def _get_active_session_name(self, chat_id: int) -> str:
        """Get the active session name for a chat.

        Args:
            chat_id: Telegram chat ID.

        Returns:
            Active session name, defaults to "main".
        """
        return self.active_sessions.get(chat_id, "main")

    def get_or_create(
        self, chat_id: int, cwd: str | None = None, name: str | None = None
    ) -> Session:
        """Get existing active session or create new one.

        Args:
            chat_id: Telegram chat ID.
            cwd: Working directory (uses default if not specified).
            name: Session name (uses active session if not specified).

        Returns:
            The session for this chat.
        """
        if chat_id not in self.sessions:
            self.sessions[chat_id] = {}
            self.active_sessions[chat_id] = "main"

        session_name = name or self._get_active_session_name(chat_id)

        if session_name not in self.sessions[chat_id]:
            effective_cwd = cwd or self.default_cwd
            session = Session(
                chat_id=chat_id,
                name=session_name,
                cwd=effective_cwd,
                permission_handler=PermissionHandler(
                    timeout=self.permission_timeout,
                    notify_callback=self._notify_callbacks.get(chat_id),
                ),
            )
            self.sessions[chat_id][session_name] = session
            self._persist_session(session)
            # If creating the active session name, ensure it's set
            if session_name == self._get_active_session_name(chat_id):
                self.active_sessions[chat_id] = session_name
                if self.storage:
                    self.storage.set_active_session(chat_id, session_name)

        return self.sessions[chat_id][session_name]

    async def create_new_async(
        self, chat_id: int, cwd: str | None = None, name: str | None = None
    ) -> Session:
        """Create a new session, replacing any existing one with same name.

        Args:
            chat_id: Telegram chat ID.
            cwd: Working directory.
            name: Session name (uses "main" if not specified).

        Returns:
            The new session.
        """
        if chat_id not in self.sessions:
            self.sessions[chat_id] = {}
            self.active_sessions[chat_id] = "main"

        session_name = name or "main"

        # Clean up old session if exists
        if session_name in self.sessions.get(chat_id, {}):
            old_session = self.sessions[chat_id][session_name]
            await self._close_client(old_session)

        effective_cwd = cwd or self.default_cwd
        session = Session(
            chat_id=chat_id,
            name=session_name,
            cwd=effective_cwd,
            permission_handler=PermissionHandler(
                timeout=self.permission_timeout,
                notify_callback=self._notify_callbacks.get(chat_id),
            ),
        )
        self.sessions[chat_id][session_name] = session
        self.active_sessions[chat_id] = session_name
        self._persist_session(session)
        if self.storage:
            self.storage.set_active_session(chat_id, session_name)
        return session

    def create_new(
        self, chat_id: int, cwd: str | None = None, name: str | None = None
    ) -> Session:
        """Create a new session synchronously (closes client in background).

        Args:
            chat_id: Telegram chat ID.
            cwd: Working directory.
            name: Session name (uses "main" if not specified).

        Returns:
            The new session.
        """
        if chat_id not in self.sessions:
            self.sessions[chat_id] = {}
            self.active_sessions[chat_id] = "main"

        session_name = name or "main"

        # Clean up old session if exists
        if session_name in self.sessions.get(chat_id, {}):
            old_session = self.sessions[chat_id][session_name]
            if old_session.sdk_client is not None:
                asyncio.create_task(self._close_client(old_session))

        effective_cwd = cwd or self.default_cwd
        session = Session(
            chat_id=chat_id,
            name=session_name,
            cwd=effective_cwd,
            permission_handler=PermissionHandler(
                timeout=self.permission_timeout,
                notify_callback=self._notify_callbacks.get(chat_id),
            ),
        )
        self.sessions[chat_id][session_name] = session
        self.active_sessions[chat_id] = session_name
        self._persist_session(session)
        if self.storage:
            self.storage.set_active_session(chat_id, session_name)
        return session

    def get(self, chat_id: int, name: str | None = None) -> Session | None:
        """Get session for a chat if it exists.

        Args:
            chat_id: Telegram chat ID.
            name: Session name (uses active session if not specified).

        Returns:
            Session or None.
        """
        if chat_id not in self.sessions:
            return None

        session_name = name or self._get_active_session_name(chat_id)
        return self.sessions[chat_id].get(session_name)

    def list_sessions(self, chat_id: int) -> list[SessionInfo]:
        """List all sessions for a chat.

        Args:
            chat_id: Telegram chat ID.

        Returns:
            List of SessionInfo objects.
        """
        if chat_id not in self.sessions:
            return []

        active = self._get_active_session_name(chat_id)
        return [
            SessionInfo(
                name=session.name,
                message_count=session.message_count,
                cwd=session.cwd,
                is_active=session.name == active,
            )
            for session in self.sessions[chat_id].values()
        ]

    def get_active_session_name(self, chat_id: int) -> str | None:
        """Get the name of the active session.

        Args:
            chat_id: Telegram chat ID.

        Returns:
            Active session name or None if no sessions.
        """
        if chat_id not in self.sessions:
            return None
        return self._get_active_session_name(chat_id)

    def switch_session(self, chat_id: int, name: str) -> Session | None:
        """Switch to a different session.

        Args:
            chat_id: Telegram chat ID.
            name: Session name to switch to.

        Returns:
            The switched-to session, or None if not found.
        """
        if chat_id not in self.sessions:
            return None

        if name not in self.sessions[chat_id]:
            return None

        self.active_sessions[chat_id] = name
        if self.storage:
            self.storage.set_active_session(chat_id, name)
        return self.sessions[chat_id][name]

    def generate_session_name(self, chat_id: int) -> str:
        """Generate a unique session name for a chat.

        Args:
            chat_id: Telegram chat ID.

        Returns:
            A unique session name like "session-2", "session-3", etc.
        """
        if chat_id not in self.sessions:
            return "session-2"

        existing = set(self.sessions[chat_id].keys())
        counter = 2
        while f"session-{counter}" in existing:
            counter += 1
        return f"session-{counter}"

    def rename_session(self, chat_id: int, old_name: str, new_name: str) -> bool:
        """Rename a session.

        Args:
            chat_id: Telegram chat ID.
            old_name: Current session name.
            new_name: New session name.

        Returns:
            True if renamed, False if not found or name already exists.
        """
        if chat_id not in self.sessions:
            return False

        if old_name not in self.sessions[chat_id]:
            return False

        if new_name in self.sessions[chat_id]:
            return False

        session = self.sessions[chat_id].pop(old_name)
        session.name = new_name
        self.sessions[chat_id][new_name] = session

        if self.active_sessions.get(chat_id) == old_name:
            self.active_sessions[chat_id] = new_name

        if self.storage:
            self.storage.rename_session(chat_id, old_name, new_name)

        return True

    def set_cwd(self, chat_id: int, cwd: str) -> Session:
        """Set the working directory for the active session.

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
                """Handle tool permission requests via the session's handler."""
                (
                    approved,
                    deny_message,
                ) = await session.permission_handler.request_permission(
                    tool_name, input_data
                )
                if approved:
                    return PermissionResultAllow()
                return PermissionResultDeny(message=deny_message or "Permission denied")

            options = ClaudeAgentOptions(
                cwd=session.cwd,
                can_use_tool=permission_callback,
                cli_path=cli_path,
                # Load user, project, and local settings (CLAUDE.md, MCP servers, etc.)
                setting_sources=["user", "project", "local"],
            )
            session.sdk_client = ClaudeSDKClient(options=options)
            await session.sdk_client.__aenter__()
            logger.info(
                "Created new SDK client for chat %s session %s (CLI: %s)",
                session.chat_id,
                session.name,
                cli_path,
            )

        return session.sdk_client

    async def _close_client(self, session: Session) -> None:
        """Close the SDK client for a session.

        Args:
            session: The session whose client to close.
        """
        if session.sdk_client is not None:
            client = session.sdk_client
            session.sdk_client = None

            # The SDK client cannot be closed from a different async task than
            # where it was created. Instead of calling __aexit__, we directly
            # terminate the underlying subprocess to avoid spinning task groups.
            try:
                transport = getattr(client, "_transport", None)
                if transport is not None:
                    process = getattr(transport, "_process", None)
                    if process is not None:
                        process.terminate()
                        logger.info("Terminated SDK client subprocess")
            except Exception as e:
                logger.warning("Error terminating SDK client: %s", e)

    async def send_prompt(
        self, chat_id: int, prompt: str, resume: bool = True
    ) -> AsyncIterator[str]:
        """Send a prompt to the active session and stream responses.

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
                elif isinstance(msg, ResultMessage) and msg.total_cost_usd:
                    logger.info(
                        "Chat %s session %s cost: $%.4f",
                        chat_id,
                        session.name,
                        msg.total_cost_usd,
                    )

            # Persist updated session
            self._persist_session(session)

        except ImportError:
            yield "Error: claude-agent-sdk not installed."
        except Exception as e:
            logger.exception("Error in send_prompt for chat %s", chat_id)
            yield f"Error: {e}"
            # Close client on error so it can be recreated
            await self._close_client(session)

    def get_status(self, chat_id: int) -> str | None:
        """Get status of the active session.

        Args:
            chat_id: Telegram chat ID.

        Returns:
            Status string or None if no session.
        """
        session = self.get(chat_id)
        if not session:
            return None
        return session.get_status()

    async def close_session_async(self, chat_id: int, name: str) -> bool:
        """Close a specific session asynchronously.

        Args:
            chat_id: Telegram chat ID.
            name: Session name to close.

        Returns:
            True if session was closed, False if not found.
        """
        if chat_id not in self.sessions:
            return False

        if name not in self.sessions[chat_id]:
            return False

        session = self.sessions[chat_id][name]
        await self._close_client(session)

        del self.sessions[chat_id][name]

        if self.storage:
            self.storage.delete_session(chat_id, name)

        # Update active session if we closed the active one
        if self.active_sessions.get(chat_id) == name:
            if self.sessions[chat_id]:
                new_active = next(iter(self.sessions[chat_id]))
                self.active_sessions[chat_id] = new_active
                if self.storage:
                    self.storage.set_active_session(chat_id, new_active)
            else:
                del self.sessions[chat_id]
                del self.active_sessions[chat_id]

        return True

    def close_session(self, chat_id: int, name: str) -> bool:
        """Close a specific session synchronously.

        Args:
            chat_id: Telegram chat ID.
            name: Session name to close.

        Returns:
            True if session was closed, False if not found.
        """
        if chat_id not in self.sessions:
            return False

        if name not in self.sessions[chat_id]:
            return False

        session = self.sessions[chat_id][name]
        if session.sdk_client is not None:
            asyncio.create_task(self._close_client(session))

        del self.sessions[chat_id][name]

        if self.storage:
            self.storage.delete_session(chat_id, name)

        # Update active session if we closed the active one
        if self.active_sessions.get(chat_id) == name:
            if self.sessions[chat_id]:
                new_active = next(iter(self.sessions[chat_id]))
                self.active_sessions[chat_id] = new_active
                if self.storage:
                    self.storage.set_active_session(chat_id, new_active)
            else:
                del self.sessions[chat_id]
                del self.active_sessions[chat_id]

        return True

    # Legacy compatibility methods

    async def delete_session_async(self, chat_id: int) -> bool:
        """Delete the active session asynchronously (legacy compatibility).

        Args:
            chat_id: Telegram chat ID.

        Returns:
            True if session was deleted, False if not found.
        """
        name = self._get_active_session_name(chat_id)
        return await self.close_session_async(chat_id, name)

    def delete_session(self, chat_id: int) -> bool:
        """Delete the active session synchronously (legacy compatibility).

        Args:
            chat_id: Telegram chat ID.

        Returns:
            True if session was deleted, False if not found.
        """
        name = self._get_active_session_name(chat_id)
        return self.close_session(chat_id, name)

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
