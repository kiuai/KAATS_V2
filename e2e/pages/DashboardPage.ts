import type { Page, Locator } from '@playwright/test'

export class DashboardPage {
  readonly page: Page
  readonly heading: Locator
  readonly systemCards: Locator

  constructor(page: Page) {
    this.page = page
    this.heading = page.getByRole('heading', { name: /dashboard/i })
    this.systemCards = page.locator('[data-testid="system-card"], .system-card')
  }

  async goto() {
    await this.page.goto('/dashboard')
    await this.page.waitForLoadState('networkidle')
  }

  async isLoaded(): Promise<boolean> {
    try {
      await this.heading.waitFor({ timeout: 5_000 })
      return true
    } catch {
      return false
    }
  }
}
