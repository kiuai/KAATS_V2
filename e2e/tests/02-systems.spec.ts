/**
 * E2E — Systems management
 *
 * Verifies:
 *  - Systems list page renders without error.
 *  - Creating a new system via the modal appears in the list.
 *  - Navigating to a system detail page loads correctly.
 */

import { expect } from '@playwright/test'
import { test } from '../fixtures/auth'
import { SystemsPage } from '../pages/SystemsPage'

const UNIQUE_NAME = `E2E System ${Date.now()}`

test.describe('Systems', () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    const systems = new SystemsPage(page)
    await systems.goto()
  })

  test('systems list page renders', async ({ authenticatedPage: page }) => {
    // The page should render a heading or the "New System" button — not a crash screen.
    const newBtn = page.getByRole('button', { name: /new system|add system/i })
    await expect(newBtn).toBeVisible({ timeout: 8_000 })
  })

  test('create a new system and it appears in the list', async ({ authenticatedPage: page }) => {
    const systems = new SystemsPage(page)

    await systems.openNewSystemModal()

    await systems.fillNewSystemForm({
      name: UNIQUE_NAME,
      baseUrl: 'https://example-e2e.kaats.kiu.ai',
      type: 'web',
    })

    // Intercept the POST to confirm it was made
    const [response] = await Promise.all([
      page.waitForResponse((resp) =>
        resp.url().includes('/systems') && resp.request().method() === 'POST'
      ),
      systems.submitNewSystem(),
    ])

    expect(response.status()).toBeLessThan(300)

    // After creation the modal closes and the new card appears
    const card = await systems.getSystemCardByName(UNIQUE_NAME)
    await expect(card).toBeVisible({ timeout: 8_000 })
  })

  test('system detail page loads from list click', async ({ authenticatedPage: page }) => {
    // Navigate to the first visible system card and click through
    const firstSystemLink = page.getByRole('link').filter({ hasText: /view|open|detail/i }).first()
    const anySystemCard = page.locator('a[href*="/systems/"]').first()

    const target = (await firstSystemLink.isVisible()) ? firstSystemLink : anySystemCard

    if (await target.isVisible()) {
      await target.click()
      await expect(page).toHaveURL(/\/systems\/[^/]+/, { timeout: 8_000 })
      // Should not be a full-page error
      await expect(page.getByText(/something went wrong|unhandled error/i)).not.toBeVisible()
    } else {
      test.skip(true, 'No systems available to click into')
    }
  })
})
