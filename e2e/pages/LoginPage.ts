import type { Page, Locator } from '@playwright/test'

export class LoginPage {
  readonly page: Page
  readonly devLoginButton: Locator

  constructor(page: Page) {
    this.page = page
    // The dev login button renders "Sign in (Dev)" text when VITE_DEV=true
    this.devLoginButton = page.getByRole('button', { name: /sign in \(dev\)/i })
  }

  async goto() {
    await this.page.goto('/login')
  }

  async devLogin() {
    await this.devLoginButton.click()
    // Wait for navigation away from /login — dashboard redirect
    await this.page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 10_000 })
  }
}
