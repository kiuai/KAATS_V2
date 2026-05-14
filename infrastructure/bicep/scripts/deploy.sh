#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# KAATS — Full Deployment Script
# Usage: ./infrastructure/bicep/scripts/deploy.sh [dev|staging|prod] [image-tag]
#
# Steps:
#   1. Validate Bicep (az bicep build)
#   2. What-if preview
#   3. Confirm with user
#   4. Deploy infrastructure
#   5. Populate Key Vault secrets
#   6. Build + push container images
#   7. Update Container App revisions (force new revision)
#   8. Run database migrations
#   9. Health check all endpoints
#  10. Print deployment summary
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Args ──────────────────────────────────────────────────────────────────────
ENVIRONMENT="${1:-dev}"
IMAGE_TAG="${2:-$(git rev-parse --short HEAD 2>/dev/null || echo 'latest')}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BICEP_DIR="${SCRIPT_DIR}/.."
PARAMS_FILE="${BICEP_DIR}/parameters/${ENVIRONMENT}.bicepparam"
MAIN_BICEP="${BICEP_DIR}/main.bicep"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; exit 1; }
step()    { echo -e "\n${BOLD}══ $* ${RESET}"; }

# ── Prereq checks ─────────────────────────────────────────────────────────────
step "Checking prerequisites"
command -v az    >/dev/null || error "az CLI not found"
command -v docker >/dev/null || error "docker not found"
az account show  >/dev/null || error "Not logged in — run: az login"
info "Azure subscription: $(az account show --query name -o tsv)"
info "Environment:        ${ENVIRONMENT}"
info "Image tag:          ${IMAGE_TAG}"

[[ -f "${PARAMS_FILE}" ]] || error "Parameter file not found: ${PARAMS_FILE}"

# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Validate Bicep
# ─────────────────────────────────────────────────────────────────────────────
step "1/10  Validating Bicep templates"
az bicep build --file "${MAIN_BICEP}" --stdout >/dev/null
success "Bicep validation passed"

# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — What-if preview
# ─────────────────────────────────────────────────────────────────────────────
step "2/10  Running what-if preview"
DEPLOYMENT_NAME="kaats-${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S)"

az deployment sub what-if \
  --location eastus \
  --template-file "${MAIN_BICEP}" \
  --parameters "${PARAMS_FILE}" \
  --parameters imageTag="${IMAGE_TAG}" \
  --name "${DEPLOYMENT_NAME}-whatif" \
  || warn "What-if returned non-zero (may be preview-only features)"

# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Confirm
# ─────────────────────────────────────────────────────────────────────────────
step "3/10  Confirmation"
if [[ "${ENVIRONMENT}" == "prod" ]]; then
  echo -e "${RED}${BOLD}PRODUCTION DEPLOYMENT${RESET}"
fi
read -rp "Deploy to ${ENVIRONMENT} with tag '${IMAGE_TAG}'? [y/N] " confirm
[[ "${confirm}" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Deploy infrastructure
# ─────────────────────────────────────────────────────────────────────────────
step "4/10  Deploying infrastructure"
DEPLOY_OUTPUT=$(az deployment sub create \
  --location eastus \
  --template-file "${MAIN_BICEP}" \
  --parameters "${PARAMS_FILE}" \
  --parameters imageTag="${IMAGE_TAG}" \
  --name "${DEPLOYMENT_NAME}" \
  --output json)

RG_NAME=$(echo "${DEPLOY_OUTPUT}" | jq -r '.properties.outputs.resourceGroupName.value')
ACR_SERVER=$(echo "${DEPLOY_OUTPUT}" | jq -r '.properties.outputs.acrLoginServer.value')
KV_NAME=$(echo "${DEPLOY_OUTPUT}" | jq -r '.properties.outputs.keyVaultName.value')
API_URL=$(echo "${DEPLOY_OUTPUT}" | jq -r '.properties.outputs.apiUrl.value')
FRONTEND_URL=$(echo "${DEPLOY_OUTPUT}" | jq -r '.properties.outputs.frontendUrl.value')
STORAGE_ACCOUNT=$(echo "${DEPLOY_OUTPUT}" | jq -r '.properties.outputs.storageAccountName.value')

success "Infrastructure deployed. Resource group: ${RG_NAME}"

# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Populate Key Vault secrets
# ─────────────────────────────────────────────────────────────────────────────
step "5/10  Populating Key Vault secrets"

ENV_FILE="${SCRIPT_DIR}/../../../.env.${ENVIRONMENT}"
if [[ -f "${ENV_FILE}" ]]; then
  info "Loading secrets from ${ENV_FILE}"
  # shellcheck disable=SC1090
  set -a; source "${ENV_FILE}"; set +a
else
  warn "No .env.${ENVIRONMENT} file found — will prompt for secrets interactively"
fi

set_secret() {
  local name="$1" envvar="$2"
  local value="${!envvar:-}"
  if [[ -z "${value}" ]]; then
    read -rsp "  Enter value for ${name} (Key Vault secret): " value
    echo
  fi
  az keyvault secret set \
    --vault-name "${KV_NAME}" \
    --name "${name}" \
    --value "${value}" \
    --output none
  success "  Set: ${name}"
}

set_secret "secret-key"                          "SECRET_KEY"
set_secret "azure-client-secret"                 "AZURE_CLIENT_SECRET"
set_secret "azure-openai-api-key"                "AZURE_OPENAI_API_KEY"
set_secret "azure-cosmos-key"                    "AZURE_COSMOS_KEY"
set_secret "azure-service-bus-connection-string" "AZURE_SERVICE_BUS_CONNECTION_STRING"
set_secret "azure-storage-account-key"           "AZURE_STORAGE_ACCOUNT_KEY"
set_secret "azure-sql-password"                  "AZURE_SQL_PASSWORD"

success "Key Vault secrets populated"

# ─────────────────────────────────────────────────────────────────────────────
# Step 6 — Build + push images
# ─────────────────────────────────────────────────────────────────────────────
step "6/10  Building and pushing container images"
"${SCRIPT_DIR}/build-push-images.sh" "${ACR_SERVER}" "${IMAGE_TAG}"

# ─────────────────────────────────────────────────────────────────────────────
# Step 7 — Update Container App revisions (force redeploy with new image tag)
# ─────────────────────────────────────────────────────────────────────────────
step "7/10  Updating Container App revisions"

SUFFIX="kaats-${ENVIRONMENT}"
declare -A APP_IMAGE_MAP=(
  ["ca-api-${SUFFIX}"]="${ACR_SERVER}/kaats/api:${IMAGE_TAG}"
  ["ca-worker-${SUFFIX}"]="${ACR_SERVER}/kaats/worker:${IMAGE_TAG}"
  ["ca-scheduler-${SUFFIX}"]="${ACR_SERVER}/kaats/scheduler:${IMAGE_TAG}"
  ["ca-frontend-${SUFFIX}"]="${ACR_SERVER}/kaats/frontend:${IMAGE_TAG}"
)

for app_name in "${!APP_IMAGE_MAP[@]}"; do
  image="${APP_IMAGE_MAP[$app_name]}"
  container="${app_name#ca-}"        # strip ca- prefix to get container name
  container="${container%-${SUFFIX}}" # strip -suffix to get base container name
  info "  Updating ${app_name} → ${image}"
  az containerapp update \
    --name "${app_name}" \
    --resource-group "${RG_NAME}" \
    --image "${image}" \
    --output none
done

# Update the agent-runner job image too
az containerapp job update \
  --name "job-agent-runner-${SUFFIX}" \
  --resource-group "${RG_NAME}" \
  --image "${ACR_SERVER}/kaats/worker:${IMAGE_TAG}" \
  --output none
success "Container App revisions updated"

# ─────────────────────────────────────────────────────────────────────────────
# Step 8 — Run database migrations
# ─────────────────────────────────────────────────────────────────────────────
step "8/10  Running database migrations"
"${SCRIPT_DIR}/run-migrations.sh" "${RG_NAME}" "ca-api-${SUFFIX}"

# ─────────────────────────────────────────────────────────────────────────────
# Step 9 — Health checks
# ─────────────────────────────────────────────────────────────────────────────
step "9/10  Health checks"

check_endpoint() {
  local url="$1" label="$2" attempts=12 delay=10
  info "  Checking ${label}: ${url}"
  for i in $(seq 1 "${attempts}"); do
    status=$(curl -sL -o /dev/null -w '%{http_code}' --max-time 10 "${url}" 2>/dev/null || echo '000')
    if [[ "${status}" == "200" ]]; then
      success "  ${label} — HTTP ${status}"
      return 0
    fi
    warn "  Attempt ${i}/${attempts}: HTTP ${status} — retrying in ${delay}s…"
    sleep "${delay}"
  done
  error "${label} health check failed after ${attempts} attempts (last status: ${status})"
}

check_endpoint "${API_URL}/health/live"  "API liveness"
check_endpoint "${API_URL}/health/ready" "API readiness"
check_endpoint "${FRONTEND_URL}"         "Frontend"

# ─────────────────────────────────────────────────────────────────────────────
# Step 10 — Summary
# ─────────────────────────────────────────────────────────────────────────────
step "10/10  Deployment summary"
echo -e "
${BOLD}KAATS ${ENVIRONMENT} deployment complete${RESET}
  Environment:     ${ENVIRONMENT}
  Image tag:       ${IMAGE_TAG}
  Resource group:  ${RG_NAME}
  ACR:             ${ACR_SERVER}
  Key Vault:       ${KV_NAME}
  Storage:         ${STORAGE_ACCOUNT}
  API:             ${API_URL}
  Frontend:        ${FRONTEND_URL}
  API docs:        ${API_URL}/docs  (non-prod only)

${GREEN}${BOLD}Deployment succeeded.${RESET}
"
