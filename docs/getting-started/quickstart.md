# Quickstart

Get voice-agent running in 5 minutes.

## Prerequisites

- A Telegram bot token (from @BotFather)
- A running whisper-server
- Claude CLI installed and authenticated (`claude login`)

## Step 1: Clone and Configure

```bash
git clone https://github.com/paolino/voice-agent
cd voice-agent

# Create .env file
cat > .env << EOF
TELEGRAM_BOT_TOKEN=your-bot-token
WHISPER_URL=http://localhost:8080/transcribe
ALLOWED_CHAT_IDS=your-chat-id
EOF
```

## Step 2: Run the Bot

```bash
# Using Nix
nix run

# Or using Python directly
python -m voice_agent
```

## Step 3: Test It

1. Open Telegram and find your bot
2. Send `/start` to see the welcome message
3. Send a voice message saying "list files"
4. The bot will transcribe your message and show Claude's response

## Basic Voice Commands

| Say this | What happens |
|----------|--------------|
| "list files" | Lists files in current directory |
| "status" | Shows session status |
| "new session" | Starts a fresh session |
| "yes" / "approve" | Approves a pending permission |
| "no" / "reject" | Rejects a pending permission |

## Next Steps

- [Configure projects](configuration.md) for easy directory switching
- [Learn all voice commands](../guides/voice-commands.md)
- [Set up deployment](../guides/deployment.md) for production use
