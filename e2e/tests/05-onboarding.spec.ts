/**
 * E2E — Onboarding & invitation flow
 *
 * Verifies:
 *  - The onboarding wizard page renders.
 *  - Checklist GET /onboarding/status returns a valid object.
 *  - The accept-invite page shows "not found" for an invalid token.
 *  - Creating an invitation via API returns 201.
 */

import { expect } from '@playwright/test'
import { test } from '../fixtures/auth'

const API_URL = process.env.API_URL ?? 'http://localhost:8000'

test.describe('Onboarding', () => {
  test('wizard page renders when authenticated', async ({ authenticatedPage: page }) => {
    await page.goto('/onboarding')
    await page.waitForLoadState('networkidle')
    // Should show a step label from the wizard
    await expect(page.getByText(/company profile|invite|system|agent/i).first()).toBeVisible({
      timeout: 8_000,
    })
  })

  test('accept-invite page shows error for invalid token', async ({ page }) => {
    await page.goto('/accept-invite?token=invalid-token-that-does-not-exist')
    await page.waitForLoadState('networkidle')
    await expect(
      page.getByText(/not found|invalid|expired|does not exist/i)
    ).toBeVisible({ timeout: 8_000 })
  })

  test('GET /onboarding/status returns has_* fields', async ({ request }) => {
    const loginResp = await request.post(`${API_URL}/api/v1/auth/callback`, {
      data: { code: 'dev', redirect_uri: 'http://localhost:5173' },
    })
    const { access_token, company } = await loginResp.json()

    const resp = await request.get(`${API_URL}/api/v1/onboarding/status`, {
      headers: {
        Authorization: `Bearer ${access_token}`,
        'X-Company-Slug': company.slug,
      },
    })
    expect(resp.ok()).toBeTruthy()
    const body = await resp.json()
    expect(typeof body.has_profile).toBe('boolean')
    expect(typeof body.has_team_member).toBe('boolean')
    expect(typeof body.has_system).toBe('boolean')
    expect(typeof body.has_agent_run).toBe('boolean')
    expect(typeof body.is_complete).toBe('boolean')
  })

  test('POST /onboarding/invitations creates an invitation', async ({ request }) => {
    const loginResp = await request.post(`${API_URL}/api/v1/auth/callback`, {
      data: { code: 'dev', redirect_uri: 'http://localhost:5173' },
    })
    const { access_token, company } = await loginResp.json()

    const email = `e2e-invite-${Date.now()}@test.example.com`
    const resp = await request.post(`${API_URL}/api/v1/onboarding/invitations`, {
      headers: {
        Authorization: `Bearer ${access_token}`,
        'X-Company-Slug': company.slug,
        'Content-Type': 'application/json',
      },
      data: { email, role: 'qa' },
    })
    expect(resp.status()).toBe(201)
    const body = await resp.json()
    expect(body.email).toBe(email)
    expect(body.status).toBe('pending')
  })
})
