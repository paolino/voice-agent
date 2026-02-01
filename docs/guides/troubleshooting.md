# Troubleshooting

## Common Issues

### Bot doesn't respond to messages

**Symptoms**: Send voice messages but get no response.

**Check**:

1. Is your chat ID in `ALLOWED_CHAT_IDS`?
   ```bash
   # Find your chat ID
   curl "https://api.telegram.org/bot<TOKEN>/getUpdates"
   ```

2. Is the bot running?
   ```bash
   journalctl -u voice-agent -f
   ```

3. Is the token correct?
   ```bash
   # Test with curl
   curl "https://api.telegram.org/bot<TOKEN>/getMe"
   ```

### "Transcription failed" errors

**Symptoms**: Bot receives audio but can't transcribe.

**Check**:

1. Is whisper-server running?
   ```bash
   curl http://localhost:8080/health
   ```

2. Is `WHISPER_URL` correct?
   ```bash
   curl -X POST -F "file=@test.ogg" http://localhost:8080/transcribe
   ```

3. Is the audio format supported? Telegram sends `.oga` (Opus in Ogg).

### "claude CLI not found"

**Symptoms**: Transcription works but Claude doesn't respond.

**Check**:

1. Is Claude CLI installed?
   ```bash
   which claude
   claude --version
   ```

2. Is Claude CLI authenticated?
   ```bash
   claude login
   ```

3. Is Claude CLI in the service's PATH?

### Permission requests never complete

**Symptoms**: Asked to approve but approval doesn't work.

**Check**:

1. Say the exact keywords: "yes", "approve", "ok"
2. Check for pending permissions: say "status"
3. Approval might have timed out (default: 5 minutes)

### Session state is wrong

**Symptoms**: Claude seems confused or in wrong directory.

**Fix**: Say "new session" to reset.

## Debug Mode

Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or set environment:

```bash
export PYTHONUNBUFFERED=1
export LOG_LEVEL=DEBUG
```

## Log Locations

| Method | Location |
|--------|----------|
| Direct run | stdout |
| systemd | `journalctl -u voice-agent` |
| Docker | `docker logs voice-agent` |

## Getting Help

1. Check logs for error messages
2. Try "status" command to see session state
3. Say "new session" to reset
4. Restart the service if needed

## Known Limitations

- **No voice responses**: Output is text only
- **Single session per chat**: Can't run parallel Claude sessions
- **Memory-based sessions**: Sessions don't persist across restarts
- **No image support**: Can't process screenshots or images
