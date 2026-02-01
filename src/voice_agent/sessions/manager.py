"""Session management for Claude Code SDK.

Manages Claude SDK client instances and their lifecycle.
"""

import asyncio
import subprocess
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from voice_agent.sessions.permissions import PermissionHandler


@dataclass
class Session:
    """A Claude Code session.

    Attributes:
        chat_id: Telegram chat ID this session belongs to.
        cwd: Working directory for the session.
        created_at: When the session was created.
        message_count: Number of messages exchanged.
        permission_handler: Handler for permission requests.
        process: The Claude subprocess if running.
    """

    chat_id: int
    cwd: str
    created_at: datetime = field(default_factory=datetime.now)
    message_count: int = 0
    permission_handler: PermissionHandler = field(default_factory=PermissionHandler)
    process: subprocess.Popen[str] | None = None

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
    """

    def __init__(
        self,
        default_cwd: str = "/code",
        permission_timeout: int = 300,
    ) -> None:
        """Initialize the session manager.

        Args:
            default_cwd: Default working directory for new sessions.
            permission_timeout: Timeout in seconds for permission requests.
        """
        self.sessions: dict[int, Session] = {}
        self.default_cwd = default_cwd
        self.permission_timeout = permission_timeout
        self._notify_callbacks: dict[int, Any] = {}

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
        return self.sessions[chat_id]

    def create_new(self, chat_id: int, cwd: str | None = None) -> Session:
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
            if old_session.process:
                old_session.process.terminate()

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
        return session

    async def send_prompt(
        self, chat_id: int, prompt: str
    ) -> AsyncIterator[str]:
        """Send a prompt to the session and stream responses.

        This uses the Claude CLI in a subprocess for now.
        Future versions will use the SDK directly.

        Args:
            chat_id: Telegram chat ID.
            prompt: The prompt to send.

        Yields:
            Response chunks from Claude.
        """
        session = self.get_or_create(chat_id)
        session.message_count += 1

        # Use Claude CLI with --print flag for non-interactive output
        cmd = [
            "claude",
            "--print",
            "--dangerously-skip-permissions",
            prompt,
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=session.cwd,
            )

            buffer = ""
            while True:
                if process.stdout is None:
                    break

                chunk = await process.stdout.read(1024)
                if not chunk:
                    break

                text = chunk.decode("utf-8", errors="replace")
                buffer += text

                # Yield complete lines
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        yield line

            # Yield any remaining content
            if buffer.strip():
                yield buffer.strip()

            await process.wait()

            # Check for errors
            if process.returncode != 0 and process.stderr:
                stderr = await process.stderr.read()
                if stderr:
                    yield f"Error: {stderr.decode('utf-8', errors='replace')}"

        except FileNotFoundError:
            yield "Error: claude CLI not found. Make sure it's installed and in PATH."
        except Exception as e:
            yield f"Error: {e}"

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
