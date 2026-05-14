/**
 * E2E — Usage & quota
 *
 * Verifies:
 *  - GET /usage/quota returns quota data (plan_tier, tokens_*, runs_*).
 *  - The AI Usage page renders the quota section.
 *  - Quota bars are visible.
 */

import { expect } from '@playwright/test'
import { test } from '../fixtures/auth'

const API_URL = process.env.API_URL ?? 'http://localhost:8000'

test.describe('Usage & Quota', () => {
  test('GET /usage/quota returns expected schema', async ({ request }) => {
    const loginResp = await request.post(`${API_URL}/api/v1/auth/callback`, {
      data: { code: 'dev', redirect_uri: 'http://localhost:5173' },
    })
    const { access_token, company } = await loginResp.json()

    const resp = await request.get(`${API_URL}/api/v1/usage/quota`, {
      headers: {
        Authorization: `Bearer ${access_token}`,
        'X-Company-Slug': company.slug,
      },
    })
    expect(resp.ok()).toBeTruthy()
    const body = await resp.json()

    expect(typeof body.plan_tier).toBe('string')
    expect(typeof body.tokens_used).toBe('number')
    expect(typeof body.tokens_warning).toBe('boolean')
    expect(typeof body.tokens_exceeded).toBe('boolean')
    expect(typeof body.runs_used).toBe('number')
    expect(typeof body.runs_warning).toBe('boolean')
    expect(typeof body.runs_exceeded).toBe('boolean')
  })

  test('new company starts with free plan tier', async ({ request }) => {
    const loginResp = await request.post(`${API_URL}/api/v1/auth/callback`, {
      data: { code: 'dev', redirect_uri: 'http://localhost:5173' },
    })
    const { access_token, company } = await loginResp.json()

    const resp = await request.get(`${API_URL}/api/v1/usage/quota`, {
      headers: {
        Authorization: `Bearer ${access_token}`,
        'X-Company-Slug': company.slug,
      },
    })
    const body = await resp.json()
    // New company has no CompanyPlan row → defaults to free
    expect(body.plan_tier).toBe('free')
  })

  test('AI Usage page renders quota bars', async ({ authenticatedPage: page }) => {
    await page.goto('/reports/ai-usage')
    await page.waitForLoadState('networkidle')

    // Quota section heading
    await expect(page.getByText(/this month.s quota|quota/i)).toBeVisible({ timeout: 10_000 })

    // Progress bar elements (the coloured bars)
    const bars = page.locator('.rounded-full.h-2')
    await expect(bars.first()).toBeVisible({ timeout: 8_000 })
  })

  test('usage history endpoint returns array', async ({ request }) => {
    const loginResp = await request.post(`${API_URL}/api/v1/auth/callback`, {
      data: { code: 'dev', redirect_uri: 'http://localhost:5173' },
    })
    const { access_token, company } = await loginResp.json()

    const resp = await request.get(`${API_URL}/api/v1/usage/history?months=3`, {
      headers: {
        Authorization: `Bearer ${access_token}`,
        'X-Company-Slug': company.slug,
      },
    })
    expect(resp.ok()).toBeTruthy()
    const body = await resp.json()
    expect(Array.isArray(body)).toBeTruthy()
  })
})
