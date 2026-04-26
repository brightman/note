#!/usr/bin/env bash
# Run the integration test suite.
#
# Two modes:
#   --docker   Use docker compose for postgres + minio (default when docker is available)
#   --local    Use local PostgreSQL + moto S3 server (no docker needed)
#
# Usage:
#   ./scripts/run_integration.sh                # auto-detect
#   ./scripts/run_integration.sh --local        # force local mode
#   ./scripts/run_integration.sh --docker       # force docker mode
#   ./scripts/run_integration.sh -k users       # pass pytest filters
#   ./scripts/run_integration.sh --no-down      # keep services after tests (docker mode)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$ROOT/deploy/docker-compose.test.yaml"
CP_DIR="$ROOT/control-plane"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[integration]${NC} $*"; }
warn()  { echo -e "${YELLOW}[integration]${NC} $*"; }
error() { echo -e "${RED}[integration]${NC} $*" >&2; }

# ── parse args ────────────────────────────────────────────────────────────────
MODE="auto"
NO_DOWN=0
PYTEST_EXTRA=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --docker)  MODE="docker"; shift ;;
        --local)   MODE="local";  shift ;;
        --no-down) NO_DOWN=1;     shift ;;
        *)         PYTEST_EXTRA+=("$1"); shift ;;
    esac
done

# Auto-detect
if [[ "$MODE" == "auto" ]]; then
    if docker info &>/dev/null 2>&1; then
        MODE="docker"
    else
        MODE="local"
    fi
fi
info "mode: $MODE"

# ── install Python deps ───────────────────────────────────────────────────────
info "checking Python dependencies..."
pip install --quiet \
    pytest pytest-asyncio anyio httpx \
    fastapi "uvicorn[standard]" \
    "sqlalchemy[asyncio]" asyncpg psycopg2-binary \
    pydantic pydantic-settings \
    "python-jose[cryptography]" \
    "passlib[bcrypt]" "bcrypt==4.0.1" \
    cryptography \
    "aioboto3==12.4.0" \
    "moto[s3,server]" flask \
    structlog 2>&1 | tail -2

# ── docker mode ───────────────────────────────────────────────────────────────
if [[ "$MODE" == "docker" ]]; then
    cleanup_docker() {
        [[ $NO_DOWN -eq 0 ]] && docker compose -f "$COMPOSE_FILE" down -v --remove-orphans 2>/dev/null || true
    }
    trap cleanup_docker EXIT

    info "starting docker services..."
    docker compose -f "$COMPOSE_FILE" up -d postgres-test minio-test

    for svc in postgres-test minio-test; do
        info "waiting for $svc..."
        for i in $(seq 1 30); do
            docker compose -f "$COMPOSE_FILE" ps "$svc" 2>/dev/null | grep -q "healthy" && break
            sleep 2
        done
        docker compose -f "$COMPOSE_FILE" ps "$svc" | grep -q "healthy" \
            || { error "$svc never became healthy"; exit 1; }
    done

    export NC_DATABASE_URL="postgresql+asyncpg://nanobot:nanobot@localhost:5433/nanobot_test"
    export NC_DATABASE_URL_SYNC="postgresql://nanobot:nanobot@localhost:5433/nanobot_test"
    export NC_S3_ENDPOINT="http://localhost:9002"
fi

# ── local mode: expects pg running + uses moto ────────────────────────────────
if [[ "$MODE" == "local" ]]; then
    # Check postgres
    if ! pg_isready -h localhost -p 5432 -U nanobot &>/dev/null; then
        error "PostgreSQL is not running on localhost:5432"
        error "Start it with: pg_ctlcluster 16 main start"
        exit 1
    fi
    # Ensure test DB exists
    psql "postgresql://nanobot:nanobot@localhost:5432/postgres" \
        -c "CREATE DATABASE nanobot_test" 2>/dev/null || true

    export NC_DATABASE_URL="postgresql+asyncpg://nanobot:nanobot@localhost:5432/nanobot_test"
    export NC_DATABASE_URL_SYNC="postgresql://nanobot:nanobot@localhost:5432/nanobot_test"
    export NC_S3_ENDPOINT="http://localhost:9002"  # moto started by pytest
fi

# ── common env ────────────────────────────────────────────────────────────────
export NC_S3_BUCKET="nanobot-test"
export NC_S3_ACCESS_KEY="testing"
export NC_S3_SECRET_KEY="testing"
export NC_JWT_SECRET="integration-test-secret"
export NC_ENCRYPTION_KEY="integration-test-enc-key-padded=="
export NC_VM_IDLE_TIMEOUT="1800"
export NC_VM_REAPER_INTERVAL="60"
export AWS_DEFAULT_REGION="us-east-1"
export AWS_ACCESS_KEY_ID="testing"
export AWS_SECRET_ACCESS_KEY="testing"
export PYTHONPATH="$CP_DIR"

# ── run tests ─────────────────────────────────────────────────────────────────
info "running integration tests..."
cd "$ROOT"
python -m pytest tests/integration/ \
    -v --tb=short -p no:warnings \
    "${PYTEST_EXTRA[@]+"${PYTEST_EXTRA[@]}"}"

EXIT_CODE=$?
[[ $EXIT_CODE -eq 0 ]] && info "all integration tests passed ✓" || error "some tests failed"
exit $EXIT_CODE
