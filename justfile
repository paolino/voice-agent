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

# Start local testing - stop container, run from source with localhost whisper
test-local:
    #!/usr/bin/env bash
    set -euo pipefail
    cd /code/infrastructure/compose/voice-agent
    docker compose --env-file ~/.config/voice-agent/.env stop voice-agent
    cd /code/voice-agent
    pkill -f '[v]oice-agent-wrapped' 2>/dev/null || true
    sleep 1
    set -a && source ~/.config/voice-agent/.env
    export WHISPER_URL=http://localhost:9003/transcribe
    export SESSION_STORAGE_PATH=/code/infrastructure/compose/voice-agent/data/sessions.json
    nix run . > /tmp/voice-agent.log 2>&1 &
    sleep 4
    echo "Local testing started. Logs: /tmp/voice-agent.log"

# Stop local testing - stop local bot, restart container
test-local-stop:
    #!/usr/bin/env bash
    set -euo pipefail
    pkill -f '[v]oice-agent-wrapped' 2>/dev/null || true
    cd /code/infrastructure/compose/voice-agent
    docker compose --env-file ~/.config/voice-agent/.env start voice-agent
    echo "Container restarted"

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
    #!/usr/bin/env bash
    IMAGE=$(docker images ghcr.io/paolino/voice-agent | awk 'NR==2 {print $1":"$2}')
    docker run --rm -it \
        --env-file .env \
        -e WHISPER_URL=${WHISPER_URL:-http://host.docker.internal:8080/transcribe} \
        $IMAGE

# Build and run Docker container
docker: docker-build docker-load docker-run

# Deploy locally - build, load, and restart compose stack
deploy-local:
    #!/usr/bin/env bash
    set -euo pipefail
    nix build .#docker-image
    docker load < result
    TAG=$(nix eval .#imageTag --raw)
    ENV_FILE=~/.config/voice-agent/.env
    grep -q "^VOICE_AGENT_VERSION=" "$ENV_FILE" && \
        sed -i "s/^VOICE_AGENT_VERSION=.*/VOICE_AGENT_VERSION=$TAG/" "$ENV_FILE" || \
        echo "VOICE_AGENT_VERSION=$TAG" >> "$ENV_FILE"
    cd /code/infrastructure/compose/voice-agent
    docker compose --env-file "$ENV_FILE" up -d
    echo "Deployed $TAG locally"

# Deploy to plutimus.com - fetch from Cachix and reload
deploy:
    ssh plutimus.com 'cd ~/services/voice-agent && \
        TAG=`nix eval github:paolino/voice-agent#imageTag --raw --refresh` && \
        nix build github:paolino/voice-agent#docker-image --refresh && \
        docker load < result && \
        grep -q "^VOICE_AGENT_VERSION=" .env && \
            sed -i "s/^VOICE_AGENT_VERSION=.*/VOICE_AGENT_VERSION=$TAG/" .env || \
            echo "VOICE_AGENT_VERSION=$TAG" >> .env && \
        docker compose up -d && \
        echo "Deployed $TAG"'

# Deploy branch/ref to plutimus.com (for testing)
deploy-dev ref:
    ssh plutimus.com 'cd ~/services/voice-agent && \
        TAG=`nix eval github:paolino/voice-agent/{{ref}}#imageTag --raw --refresh` && \
        nix build github:paolino/voice-agent/{{ref}}#docker-image --refresh && \
        docker load < result && \
        grep -q "^VOICE_AGENT_VERSION=" .env && \
            sed -i "s/^VOICE_AGENT_VERSION=.*/VOICE_AGENT_VERSION=$TAG/" .env || \
            echo "VOICE_AGENT_VERSION=$TAG" >> .env && \
        docker compose up -d && \
        echo "Deployed $TAG from {{ref}}"'

# Clean build artifacts
clean:
    rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov/ site/
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Install in development mode
install-dev:
    pip install -e ".[dev,test,docs]"
