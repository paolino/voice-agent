# Development commands for voice-agent

# Run the bot (foreground)
run:
    python -m voice_agent

# Start bot in background with nix (set ENV_FILE or place .env in project root)
start:
    @pkill -f '[v]oice-agent-wrapped' 2>/dev/null || true
    @sleep 1
    @bash -c 'set -a && source "${ENV_FILE:-.env}" && nix run . > /tmp/voice-agent.log 2>&1 &'
    @sleep 4
    @echo "Bot started. Logs: /tmp/voice-agent.log"

# Stop the bot
stop:
    @pkill -f '[v]oice-agent-wrapped' 2>/dev/null && echo "Bot stopped" || echo "Bot not running"

# Restart the bot
restart: stop start

# Show bot logs
logs:
    @tail -50 /tmp/voice-agent.log | grep -v getUpdates

# Follow bot logs
logs-follow:
    @tail -f /tmp/voice-agent.log | grep -v getUpdates

# Run all tests
test:
    pytest tests/ -v

# Run unit tests only
test-unit:
    pytest tests/unit/ -v -m unit

# Run integration tests
test-integration:
    pytest tests/integration/ -v -m integration

# Run e2e tests
test-e2e:
    pytest tests/e2e/ -v -m e2e

# Generate coverage report
test-coverage:
    pytest tests/ --cov=voice_agent --cov-report=html --cov-report=term

# Lint code
lint:
    ruff check src/ tests/
    mypy src/

# Format code
fmt:
    ruff format src/ tests/

# Check formatting without modifying
fmt-check:
    ruff format --check src/ tests/

# Serve docs locally
docs-serve:
    mkdocs serve

# Build docs
docs-build:
    mkdocs build

# Deploy docs to GitHub Pages
docs-deploy:
    mkdocs gh-deploy

# Build Docker image with nix
docker-build:
    nix build .#docker-image

# Load Docker image into docker daemon
docker-load:
    docker load < result

# Run Docker container (requires .env file with TELEGRAM_BOT_TOKEN)
docker-run:
    docker run --rm -it \
        --network host \
        --env-file .env \
        -e WHISPER_URL=${WHISPER_URL:-http://localhost:9003/transcribe} \
        ghcr.io/paolino/voice-agent:0.1.0

# Build and run Docker container
docker: docker-build docker-load docker-run

# Start docker-compose stack (voice-agent + whisper-server)
compose-up:
    docker compose up -d

# Stop docker-compose stack
compose-down:
    docker compose down

# Clean build artifacts
clean:
    rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov/ site/
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Install in development mode
install-dev:
    pip install -e ".[dev,test,docs]"
