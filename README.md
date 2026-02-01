# voice-agent

Voice control for Claude Code via Telegram.

Send voice messages from your phone, get them transcribed, and control Claude Code sessions hands-free.

## Documentation

https://paolino.github.io/voice-agent/

## Quick Start

1. Set environment variables:
   ```bash
   export TELEGRAM_BOT_TOKEN="your-bot-token"
   export WHISPER_URL="http://localhost:8080/transcribe"
   ```

2. Run:
   ```bash
   nix run
   ```

3. Send a voice message to your Telegram bot

## Requirements

- Telegram Bot token (from @BotFather)
- Running whisper-server instance
- Claude CLI authenticated (`claude login`)
