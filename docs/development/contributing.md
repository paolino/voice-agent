# Contributing

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/paolino/voice-agent
   cd voice-agent
   ```

2. Enter development shell:
   ```bash
   nix develop
   # or
   pip install -e ".[dev,test,docs]"
   ```

3. Run tests:
   ```bash
   just test
   ```

## Code Style

- **Formatter**: ruff format
- **Linter**: ruff check
- **Type checker**: mypy (strict mode)

Run all checks:

```bash
just lint
just fmt
```

## Project Structure

```
voice-agent/
├── src/voice_agent/     # Main package
│   ├── bot.py           # Telegram bot
│   ├── config.py        # Settings
│   ├── router.py        # Command routing
│   ├── transcribe.py    # Whisper client
│   └── sessions/        # Session management
├── tests/               # Test suite
│   ├── unit/            # Unit tests
│   ├── integration/     # Integration tests
│   └── e2e/             # End-to-end tests
└── docs/                # Documentation
```

## Making Changes

1. Create a feature branch
2. Make your changes
3. Add tests for new functionality
4. Run `just lint` and `just test`
5. Submit a pull request

## Commit Messages

Use conventional commits:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `refactor:` - Code refactoring
- `test:` - Test changes
- `chore:` - Maintenance

## Testing

```bash
# Run all tests
just test

# Run specific test category
just test-unit
just test-integration
just test-e2e

# Run with coverage
just test-coverage
```

## Documentation

```bash
# Serve docs locally
just docs-serve

# Build static site
just docs-build
```

Docs are auto-generated from docstrings using mkdocstrings.
