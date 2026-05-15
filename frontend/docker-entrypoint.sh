#!/bin/sh
set -e

# Inject runtime environment variables into the static config file.
# Azure Container Apps env vars are available here at container startup.
AZURE_CLIENT_ID="${VITE_AZURE_CLIENT_ID:-}"
AZURE_TENANT_ID="${VITE_AZURE_TENANT_ID:-common}"
API_URL="${VITE_API_URL:-/api/v1}"

cat > /usr/share/nginx/html/env.js <<EOF
window.__KAATS_CONFIG__ = {
  AZURE_CLIENT_ID: "${AZURE_CLIENT_ID}",
  AZURE_TENANT_ID: "${AZURE_TENANT_ID}",
  API_URL: "${API_URL}",
};
EOF

exec nginx -g 'daemon off;'
