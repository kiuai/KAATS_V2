// Runtime config — overwritten by docker-entrypoint.sh at container start.
// These placeholder values are replaced by envsubst from Container Apps env vars.
window.__KAATS_CONFIG__ = {
  AZURE_CLIENT_ID: "VITE_AZURE_CLIENT_ID_PLACEHOLDER",
  AZURE_TENANT_ID: "VITE_AZURE_TENANT_ID_PLACEHOLDER",
  API_URL: "VITE_API_URL_PLACEHOLDER",
};
