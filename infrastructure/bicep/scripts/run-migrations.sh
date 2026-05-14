#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# KAATS — Run Alembic Migrations
# Usage: ./run-migrations.sh <resource-group> <container-app-name>
# e.g.:  ./run-migrations.sh rg-kaats-prod ca-api-kaats-prod
#
# Executes `alembic upgrade head` inside the running API container via
# `az containerapp exec`. Waits for the API to be ready first.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

RG_NAME="${1:?Usage: $0 <resource-group> <container-app-name>}"
APP_NAME="${2:?Usage: $0 <resource-group> <container-app-name>}"

CYAN='\033[0;36m'; GREEN='\033[0;32m'; RED='\033[0;31m'
YELLOW='\033[1;33m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; exit 1; }

# ─────────────────────────────────────────────────────────────────────────────
# Wait for at least one running replica
# ─────────────────────────────────────────────────────────────────────────────
info "Waiting for ${APP_NAME} to have a running replica…"

MAX_WAIT=120
WAITED=0
INTERVAL=10

while true; do
  RUNNING=$(az containerapp replica list \
    --name "${APP_NAME}" \
    --resource-group "${RG_NAME}" \
    --query "[?properties.runningState=='Running'] | length(@)" \
    --output tsv 2>/dev/null || echo "0")

  if [[ "${RUNNING}" -gt 0 ]]; then
    success "Found ${RUNNING} running replica(s)"
    break
  fi

  if [[ "${WAITED}" -ge "${MAX_WAIT}" ]]; then
    error "No running replicas found after ${MAX_WAIT}s — cannot run migrations"
  fi

  warn "  No running replicas yet (${WAITED}/${MAX_WAIT}s elapsed) — waiting ${INTERVAL}s…"
  sleep "${INTERVAL}"
  WAITED=$((WAITED + INTERVAL))
done

# ─────────────────────────────────────────────────────────────────────────────
# Get the first running replica name
# ─────────────────────────────────────────────────────────────────────────────
REPLICA=$(az containerapp replica list \
  --name "${APP_NAME}" \
  --resource-group "${RG_NAME}" \
  --query "[?properties.runningState=='Running'] | [0].name" \
  --output tsv)

info "Running migrations on replica: ${REPLICA}"

# ─────────────────────────────────────────────────────────────────────────────
# Execute migrations
# ─────────────────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}── Alembic upgrade head ──${RESET}"

az containerapp exec \
  --name "${APP_NAME}" \
  --resource-group "${RG_NAME}" \
  --replica "${REPLICA}" \
  --container "api" \
  --command "alembic -c /app/alembic.ini upgrade head"

success "Migrations completed"

# ─────────────────────────────────────────────────────────────────────────────
# Verify current revision
# ─────────────────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}── Current revision ──${RESET}"
az containerapp exec \
  --name "${APP_NAME}" \
  --resource-group "${RG_NAME}" \
  --replica "${REPLICA}" \
  --container "api" \
  --command "alembic -c /app/alembic.ini current" \
  || warn "Could not retrieve current revision (non-fatal)"

success "Migration run complete"
