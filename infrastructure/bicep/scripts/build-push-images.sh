#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# KAATS — Build and Push Container Images
# Usage: ./build-push-images.sh <acr-login-server> <image-tag>
# e.g.:  ./build-push-images.sh acrkaatsprod.azurecr.io abc1234
#
# Builds api, worker, scheduler, frontend images and pushes to ACR.
# Uses Docker BuildKit for layer caching.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

ACR_SERVER="${1:?Usage: $0 <acr-login-server> <image-tag>}"
IMAGE_TAG="${2:?Usage: $0 <acr-login-server> <image-tag>}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

CYAN='\033[0;36m'; GREEN='\033[0;32m'; RED='\033[0;31m'
BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; exit 1; }
step()    { echo -e "\n${BOLD}── $* ${RESET}"; }

# ── Login to ACR ──────────────────────────────────────────────────────────────
step "Logging in to ACR"
az acr login --name "${ACR_SERVER%%.*}"
success "ACR login successful"

# ── Enable BuildKit ───────────────────────────────────────────────────────────
export DOCKER_BUILDKIT=1

# ─────────────────────────────────────────────────────────────────────────────
# Build + push helper
# ─────────────────────────────────────────────────────────────────────────────
build_push() {
  local name="$1"
  local context="$2"
  local dockerfile="$3"
  local target="${4:-}"

  local local_tag="kaats/${name}:${IMAGE_TAG}"
  local remote_tag="${ACR_SERVER}/${local_tag}"
  local cache_tag="${ACR_SERVER}/kaats/${name}:cache"

  step "Building ${name}"
  info "  Context:    ${context}"
  info "  Dockerfile: ${dockerfile}"
  info "  Tag:        ${remote_tag}"

  local build_args=(
    "--file" "${dockerfile}"
    "--tag"  "${remote_tag}"
    "--tag"  "${ACR_SERVER}/kaats/${name}:latest"
    "--cache-from" "type=registry,ref=${cache_tag}"
    "--build-arg" "BUILDKIT_INLINE_CACHE=1"
    "--platform" "linux/amd64"
    "--push"
  )

  if [[ -n "${target}" ]]; then
    build_args+=("--target" "${target}")
  fi

  docker buildx build "${build_args[@]}" "${context}"
  success "  Pushed: ${remote_tag}"
}

# ─────────────────────────────────────────────────────────────────────────────
# Images
# ─────────────────────────────────────────────────────────────────────────────

build_push \
  "api" \
  "${REPO_ROOT}/backend" \
  "${REPO_ROOT}/backend/Dockerfile"

build_push \
  "worker" \
  "${REPO_ROOT}/backend" \
  "${REPO_ROOT}/backend/Dockerfile.worker"

build_push \
  "scheduler" \
  "${REPO_ROOT}/backend" \
  "${REPO_ROOT}/backend/Dockerfile.scheduler"

build_push \
  "frontend" \
  "${REPO_ROOT}/frontend" \
  "${REPO_ROOT}/frontend/Dockerfile" \
  "production"

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
echo -e "\n${GREEN}${BOLD}All images pushed to ${ACR_SERVER} with tag '${IMAGE_TAG}'${RESET}"
echo "  ${ACR_SERVER}/kaats/api:${IMAGE_TAG}"
echo "  ${ACR_SERVER}/kaats/worker:${IMAGE_TAG}"
echo "  ${ACR_SERVER}/kaats/scheduler:${IMAGE_TAG}"
echo "  ${ACR_SERVER}/kaats/frontend:${IMAGE_TAG}"
