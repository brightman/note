#!/usr/bin/env bash
# Start nanobot-cloud on Mac (Docker Desktop required).
# Usage:
#   ./scripts/start-mac.sh          # start all services
#   ./scripts/start-mac.sh stop     # stop and remove containers
#   ./scripts/start-mac.sh logs     # follow logs
#   ./scripts/start-mac.sh ps       # show service status

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE="$ROOT/deploy/docker-compose.mac.yaml"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${GREEN}[nanobot-cloud]${NC} $*"; }
warn() { echo -e "${YELLOW}[nanobot-cloud]${NC} $*"; }

CMD="${1:-up}"

case "$CMD" in
  stop)
    info "stopping services..."
    docker compose -f "$COMPOSE" down
    ;;
  logs)
    docker compose -f "$COMPOSE" logs -f
    ;;
  ps)
    docker compose -f "$COMPOSE" ps
    ;;
  up|*)
    if ! docker info &>/dev/null; then
      warn "Docker is not running. Please start Docker Desktop."
      exit 1
    fi

    info "building and starting services..."
    docker compose -f "$COMPOSE" up --build -d

    info "waiting for control-plane to be ready..."
    for i in $(seq 1 30); do
      if curl -sf http://localhost:8000/health &>/dev/null; then
        break
      fi
      sleep 2
    done

    if curl -sf http://localhost:8000/health &>/dev/null; then
      info "✓ nanobot-cloud is ready!"
      echo ""
      echo "  API:           http://localhost:8000"
      echo "  Health check:  http://localhost:8000/health"
      echo "  API docs:      http://localhost:8000/docs"
      echo "  MinIO console: http://localhost:9001  (minioadmin / minioadmin123)"
      echo ""
      echo "  NOTE: Firecracker VM is not available on Mac."
      echo "        User management, config, skills, and MCP APIs work normally."
    else
      warn "service did not become healthy. Check logs:"
      warn "  ./scripts/start-mac.sh logs"
      exit 1
    fi
    ;;
esac
