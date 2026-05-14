/**
 * Auth fixtures for KAATS E2E tests.
 *
 * KAATS exposes a dev-only login endpoint:
 *   POST /api/v1/auth/callback  { code: "dev", redirect_uri: "..." }
 * which returns a JWT + user + company without any real Azure AD flow.
 *
 * The `authenticatedPage` fixture calls this endpoint, stores the token and
 * auth state in localStorage (mirroring what the real login flow does), then
 * navigates to the app — so every test that uses it starts fully logged in.
 */

import { test as base, type Page } from '@playwright/test'

const API_URL = process.env.API_URL ?? 'http://localhost:8000'

export interface AuthState {
  accessToken: string
  userId: string
  companyId: string
  companySlug: string
}

/**
 * Obtain a dev JWT from the API and return parsed auth state.
 * Skips the browser entirely — uses the fetch API via `page.evaluate`.
 */
export async function devLogin(page: Page): Promise<AuthState> {
  const resp = await page.request.post(`${API_URL}/api/v1/auth/callback`, {
    data: {
      code: 'dev',
      redirect_uri: 'http://localhost:5173',
    },
  })

  if (!resp.ok()) {
    const body = await resp.text()
    throw new Error(`Dev login failed (${resp.status()}): ${body}`)
  }

  const data = await resp.json()

  return {
    accessToken: data.access_token,
    userId: data.user.id,
    companyId: data.company.id,
    companySlug: data.company.slug,
  }
}

/**
 * Inject auth state into the page's localStorage so the React app
 * treats the session as authenticated on the next navigation.
 */
export async function injectAuthState(page: Page, auth: AuthState): Promise<void> {
  // Token storage (matches apiClient interceptor in services/api.ts)
  await page.evaluate((token) => {
    localStorage.setItem('kaats_access_token', token)
  }, auth.accessToken)

  // Zustand auth store state (matches useAuthStore hydration key)
  const storeState = {
    state: {
      accessToken: auth.accessToken,
      user: { id: auth.userId },
      currentCompany: {
        id: auth.companyId,
        slug: auth.companySlug,
      },
    },
    version: 0,
  }
  await page.evaluate((state) => {
    localStorage.setItem('kaats-auth', JSON.stringify(state))
  }, storeState)
}

// ── Extended test fixture ─────────────────────────────────────────────────────

type KaatsFixtures = {
  /** A page that is pre-authenticated via dev login. */
  authenticatedPage: Page
  /** The auth state returned by devLogin (token, IDs). */
  authState: AuthState
}

export const test = base.extend<KaatsFixtures>({
  authState: async ({ page }, use) => {
    // Navigate to a blank page first so we have a context to store into.
    await page.goto('about:blank')
    const auth = await devLogin(page)
    await use(auth)
  },

  authenticatedPage: async ({ page, authState }, use) => {
    await page.goto('about:blank')
    await injectAuthState(page, authState)
    await use(page)
  },
})

export { expect } from '@playwright/test'
