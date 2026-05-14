/**
 * E2E — Requirements
 *
 * Verifies:
 *  - Navigating to a system's requirements page works.
 *  - Creating a manual requirement succeeds.
 *  - The created requirement appears in the list.
 */

import { expect } from '@playwright/test'
import { test } from '../fixtures/auth'

const API_URL = process.env.API_URL ?? 'http://localhost:8000'

test.describe('Requirements', () => {
  let systemId: string

  test.beforeAll(async ({ request }) => {
    // Create a test system via API so we have a real systemId for navigation.
    // Use the dev token obtained directly from the API.
    const loginResp = await request.post(`${API_URL}/api/v1/auth/callback`, {
      data: { code: 'dev', redirect_uri: 'http://localhost:5173' },
    })
    const { access_token, company } = await loginResp.json()

    const sysResp = await request.post(`${API_URL}/api/v1/systems`, {
      headers: {
        Authorization: `Bearer ${access_token}`,
        'X-Company-Slug': company.slug,
        'Content-Type': 'application/json',
      },
      data: {
        name: `E2E Req System ${Date.now()}`,
        base_url: 'https://req-test.example.com',
        system_type: 'web_application',
      },
    })

    if (sysResp.ok()) {
      const sys = await sysResp.json()
      systemId = sys.id
    }
  })

  test('requirements page renders for a system', async ({ authenticatedPage: page }) => {
    if (!systemId) test.skip(true, 'System creation failed in beforeAll')
    await page.goto(`/systems/${systemId}/requirements`)
    await page.waitForLoadState('networkidle')
    // Should not crash — look for either a list or an empty state
    await expect(page.getByText(/requirement|no requirements/i)).toBeVisible({ timeout: 8_000 })
  })

  test('create a manual requirement via API and it appears in UI', async ({
    authenticatedPage: page,
    request,
  }) => {
    if (!systemId) test.skip(true, 'System creation failed in beforeAll')

    // Create via API directly (faster than filling the form)
    const loginResp = await request.post(`${API_URL}/api/v1/auth/callback`, {
      data: { code: 'dev', redirect_uri: 'http://localhost:5173' },
    })
    const { access_token, company } = await loginResp.json()

    const reqTitle = `E2E Requirement ${Date.now()}`
    const reqResp = await request.post(`${API_URL}/api/v1/systems/${systemId}/requirements`, {
      headers: {
        Authorization: `Bearer ${access_token}`,
        'X-Company-Slug': company.slug,
        'Content-Type': 'application/json',
      },
      data: {
        title: reqTitle,
        description: 'Created by Playwright E2E test',
        priority: 'medium',
        source_type: 'manual',
      },
    })
    expect(reqResp.ok()).toBeTruthy()

    // Navigate to requirements page and verify
    await page.goto(`/systems/${systemId}/requirements`)
    await page.waitForLoadState('networkidle')
    await expect(page.getByText(reqTitle)).toBeVisible({ timeout: 8_000 })
  })
})
