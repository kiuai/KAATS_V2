import { PublicClientApplication } from '@azure/msal-browser'
import { msalConfig } from './msalConfig'

// Singleton MSAL instance shared by AuthProvider, api.ts, and LoginPage.
// Kept in its own module to avoid circular imports.
export const msalInstance = new PublicClientApplication(msalConfig)
