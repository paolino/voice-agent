# Configuration

voice-agent is configured via environment variables. You can also use a `.env` file.

## Required Variables

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token from @BotFather |

Note: Claude CLI uses its own authentication. Run `claude login` to authenticate.

## Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_URL` | `http://localhost:8080/transcribe` | URL of whisper-server endpoint |
| `ALLOWED_CHAT_IDS` | (empty) | Comma-separated list of allowed Telegram chat IDs. Empty allows all. |
| `DEFAULT_CWD` | `/code` | Default working directory for Claude sessions |
| `PERMISSION_TIMEOUT` | `300` | Seconds to wait for permission approval |

## Projects Configuration

Configure named projects via the `PROJECTS` environment variable as JSON:

```bash
export PROJECTS='{"whisper": "/code/whisper-server", "agent": "/code/voice-agent"}'
```

This enables commands like "work on whisper" to switch working directories.

## Example .env File

```bash
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
WHISPER_URL=http://localhost:8080/transcribe
ALLOWED_CHAT_IDS=123456789,987654321
DEFAULT_CWD=/code
PERMISSION_TIMEOUT=300
```

## Finding Your Chat ID

To find your Telegram chat ID:

1. Send a message to your bot
2. Visit: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Look for `"chat":{"id":123456789}` in the response
