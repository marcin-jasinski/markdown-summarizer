#!/usr/bin/env bash
# Smoke tests for compose.yml — run after: docker compose up -d
# Usage: bash tests/smoke/test_compose_smoke.sh
set -euo pipefail

PASS=0
FAIL=0

check() {
    local desc="$1"
    local cmd="$2"
    if eval "$cmd" > /dev/null 2>&1; then
        echo "  PASS: $desc"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== MindForge compose.yml smoke tests ==="

# 1. PostgreSQL responds to pg_isready via docker exec
check "postgres healthcheck passes" \
    "docker compose exec -T postgres pg_isready -U mindforge -d mindforge"

# 2. Redis responds to PING via docker exec
check "redis responds to PING" \
    "docker compose exec -T redis redis-cli ping | grep -q PONG"

# 3. MinIO liveness endpoint returns HTTP 200
check "minio liveness endpoint reachable" \
    "curl -sf http://localhost:9000/minio/health/live"

# 4. API health endpoint returns HTTP 200
check "api /api/health returns 200" \
    "curl -sf http://localhost:8080/api/health"

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
[[ $FAIL -eq 0 ]]
