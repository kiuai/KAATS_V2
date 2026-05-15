import type { Configuration, RedirectRequest } from '@azure/msal-browser'

// Read from runtime config (injected by docker-entrypoint.sh) first,
// then fall back to build-time baked values (for local dev with .env.local).
const runtimeConfig = (window as { __KAATS_CONFIG__?: Record<string, string> }).__KAATS_CONFIG__ ?? {}

const clientId =
  (runtimeConfig.AZURE_CLIENT_ID !== 'VITE_AZURE_CLIENT_ID_PLACEHOLDER' ? runtimeConfig.AZURE_CLIENT_ID : '') ||
  import.meta.env.VITE_AZURE_CLIENT_ID ||
  ''

const tenantId =
  (runtimeConfig.AZURE_TENANT_ID !== 'VITE_AZURE_TENANT_ID_PLACEHOLDER' ? runtimeConfig.AZURE_TENANT_ID : '') ||
  import.meta.env.VITE_AZURE_TENANT_ID ||
  'common'

export const msalConfig: Configuration = {
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri: window.location.origin + '/auth/callback',
    postLogoutRedirectUri: window.location.origin + '/login',
  },
  cache: {
    cacheLocation: 'sessionStorage',
    storeAuthStateInCookie: false,
  },
}

export const loginRequest: RedirectRequest = {
  scopes: ['openid', 'profile', 'email'],
}

export const isDev = import.meta.env.VITE_DEV_AUTH === 'true' || !clientId
