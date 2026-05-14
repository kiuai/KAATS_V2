/**
 * E2E — Authentication flow
 *
 * Verifies that:
 *  - The login page renders in dev mode with the dev login button.
 *  - Dev login navigates to /dashboard and stores the token.
 *  - Unauthenticated access to protected routes redirects to /login.
 *  - Re-loading the app with a stored token keeps the session active.
 */

import { test, expect } from '@playwright/test'
import { LoginPage } from '../pages/LoginPage'
import { DashboardPage } from '../pages/DashboardPage'
import { devLogin, injectAuthState } from '../fixtures/auth'

test.describe('Authentication', () => {
  test('login page renders the dev login button', async ({ page }) => {
    await page.goto('/login')
    const loginPage = new LoginPage(page)
    await expect(loginPage.devLoginButton).toBeVisible()
  })

  test('dev login navigates to dashboard', async ({ page }) => {
    const loginPage = new LoginPage(page)
    await loginPage.goto()
    await loginPage.devLogin()

    // Should land on /dashboard (or redirect from /)
    await expect(page).toHaveURL(/\/dashboard/)
  })

  test('dev login stores access token in localStorage', async ({ page }) => {
    const loginPage = new LoginPage(page)
    await loginPage.goto()
    await loginPage.devLogin()

    const token = await page.evaluate(() => localStorage.getItem('kaats_access_token'))
    expect(token).toBeTruthy()
    expect(typeof token).toBe('string')
    expect((token as string).split('.').length).toBe(3) // JWT has 3 parts
  })

  test('unauthenticated access redirects to /login', async ({ page }) => {
    // Clear any stored auth
    await page.goto('about:blank')
    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
    })

    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/login/, { timeout: 8_000 })
  })

  test('authenticated page load keeps session (no re-login)', async ({ page }) => {
    // Pre-inject auth state and navigate
    await page.goto('about:blank')
    const auth = await devLogin(page)
    await injectAuthState(page, auth)

    await page.goto('/dashboard')

    // Should NOT redirect to login
    await expect(page).not.toHaveURL(/\/login/)
    const dashboard = new DashboardPage(page)
    await expect(dashboard.heading).toBeVisible({ timeout: 10_000 })
  })
})
