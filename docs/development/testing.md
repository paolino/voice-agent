# Testing

## Test Structure

```
tests/
├── conftest.py          # Shared fixtures
├── unit/                # Fast, isolated tests
│   ├── test_config.py
│   ├── test_router.py
│   ├── test_transcribe.py
│   └── test_permissions.py
├── integration/         # Tests with mocked services
│   ├── test_session_manager.py
│   ├── test_bot_handlers.py
│   └── test_whisper_client.py
└── e2e/                 # Full flow tests
    └── test_voice_flow.py
```

## Running Tests

```bash
# All tests
just test

# By category
just test-unit         # Fast, no external deps
just test-integration  # Needs mocked services
just test-e2e          # Full flow tests

# With coverage
just test-coverage
```

## Test Markers

```python
@pytest.mark.unit          # Fast unit tests
@pytest.mark.integration   # Integration tests
@pytest.mark.e2e           # End-to-end tests
@pytest.mark.slow          # Long-running tests
```

## Fixtures

### Configuration

```python
@pytest.fixture
def mock_settings() -> Settings:
    """Test settings with safe defaults."""
    return Settings(
        telegram_bot_token="test-token",
        allowed_chat_ids="123,456",
    )
```

### Telegram Mocks

```python
@pytest.fixture
def mock_telegram_update() -> MagicMock:
    """Fake Telegram Update with voice message."""

@pytest.fixture
def mock_telegram_context() -> MagicMock:
    """Fake context with file download."""
```

### HTTP Mocking

```python
async def test_transcription(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://localhost:8080/transcribe",
        json={"text": "hello world"},
    )
    result = await transcribe(b"audio", "http://localhost:8080/transcribe")
    assert result == "hello world"
```

## Writing Tests

### Unit Tests

Test single functions in isolation:

```python
@pytest.mark.unit
def test_parse_approve_command():
    result = parse_command("yes")
    assert result.command_type == CommandType.APPROVE
```

### Integration Tests

Test component interactions with mocks:

```python
@pytest.mark.integration
async def test_session_creation(session_manager):
    session = session_manager.get_or_create(123)
    assert session.chat_id == 123
```

### End-to-End Tests

Test complete flows:

```python
@pytest.mark.e2e
async def test_voice_flow(e2e_bot, httpx_mock):
    httpx_mock.add_response(json={"text": "status"})
    # Simulate full voice message handling
    await e2e_bot.handle_voice(update, context)
```

## Coverage

Target: 80%+ line coverage

```bash
just test-coverage
# Opens htmlcov/index.html
```
