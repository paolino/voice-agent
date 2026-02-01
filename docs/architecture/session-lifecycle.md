# Session Lifecycle

## Overview

voice-agent maintains one Claude session per Telegram chat. Sessions track working directory, message count, and pending permissions.

## Session States

```
┌─────────────┐
│   No        │
│  Session    │
└─────────────┘
      │
      │ First message
      ▼
┌─────────────┐
│   Active    │◄────────────┐
│  Session    │             │
└─────────────┘             │
      │                     │
      │ "new session"       │ prompt/command
      ▼                     │
┌─────────────┐             │
│  Session    │─────────────┘
│  Reset      │
└─────────────┘
```

## Session Data

Each session stores:

```python
@dataclass
class Session:
    chat_id: int              # Telegram chat ID
    cwd: str                  # Working directory
    created_at: datetime      # Session start time
    message_count: int        # Messages exchanged
    permission_handler: PermissionHandler
    process: subprocess.Popen | None
```

## Creating Sessions

Sessions are created on-demand when the first message arrives:

```python
def get_or_create(self, chat_id: int, cwd: str | None = None) -> Session:
    if chat_id not in self.sessions:
        session = Session(
            chat_id=chat_id,
            cwd=cwd or self.default_cwd,
        )
        self.sessions[chat_id] = session
    return self.sessions[chat_id]
```

## Resetting Sessions

Say "new session" to reset:

```python
def create_new(self, chat_id: int, cwd: str | None = None) -> Session:
    # Clean up old session
    if chat_id in self.sessions:
        old = self.sessions[chat_id]
        if old.process:
            old.process.terminate()

    # Create fresh session
    session = Session(chat_id=chat_id, cwd=cwd or self.default_cwd)
    self.sessions[chat_id] = session
    return session
```

## Changing Working Directory

Say "work on PROJECT" to switch directories:

```python
def set_cwd(self, chat_id: int, cwd: str) -> Session:
    session = self.get_or_create(chat_id)
    session.cwd = cwd
    return session
```

## Session Status

Say "status" to see:

```
Working directory: /code/project
Messages: 15
Age: 1h 23m
Pending approval: Write file: /tmp/test.txt
```

## Memory Management

Sessions are kept in memory. For long-running deployments, consider:

- Periodic cleanup of old sessions
- Persisting session IDs to disk for resume
- Maximum session age limits
