# Multi-Session Guide

## Overview

voice-agent supports managing multiple projects from the same Telegram chat by switching working directories.

## Configuring Projects

Set up named projects in your environment:

```bash
export PROJECTS='{"whisper": "/code/whisper-server", "agent": "/code/voice-agent", "api": "/code/api-service"}'
```

Or in `.env`:

```bash
PROJECTS={"whisper": "/code/whisper-server", "agent": "/code/voice-agent"}
```

## Switching Projects

### Explicit Switch

Say "work on [project]" or "switch to [project]":

```
You: "work on whisper"
Bot: Switched to whisper (/code/whisper-server)
```

### Inline Commands

Use "on [project]: [command]" to run a single command in a project:

```
You: "on whisper: list files"
Bot: [Lists files in whisper-server directory]
```

## Project Context

After switching projects:

- All subsequent commands run in that directory
- Claude sees files from that project
- The project persists until you switch again or start a new session

## Current Session Info

Say "status" to see your current project:

```
Working directory: /code/whisper-server
Messages: 5
Age: 0h 12m
```

## Resetting

Say "new session" to reset to the default working directory:

```
You: "new session"
Bot: Started new session.
```

The new session uses `DEFAULT_CWD` (default: `/code`).

## Best Practices

1. **Name projects clearly** - Use short, memorable names
2. **Set a sensible default** - `DEFAULT_CWD` should be your most-used project
3. **Use status checks** - Verify you're in the right project before making changes
4. **Start fresh when confused** - "new session" resets everything
