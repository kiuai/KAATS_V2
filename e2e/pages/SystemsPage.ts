import type { Page, Locator } from '@playwright/test'

export class SystemsPage {
  readonly page: Page

  constructor(page: Page) {
    this.page = page
  }

  async goto() {
    await this.page.goto('/systems')
    await this.page.waitForLoadState('networkidle')
  }

  async openNewSystemModal() {
    await this.page.getByRole('button', { name: /new system|add system/i }).click()
  }

  async fillNewSystemForm(opts: {
    name: string
    baseUrl: string
    type?: string
  }) {
    await this.page.getByLabel(/name/i).fill(opts.name)
    await this.page.getByLabel(/url/i).fill(opts.baseUrl)
    if (opts.type) {
      const typeSelect = this.page.getByLabel(/type/i)
      if (await typeSelect.isVisible()) {
        await typeSelect.selectOption(opts.type)
      }
    }
  }

  async submitNewSystem() {
    await this.page.getByRole('button', { name: /create|save/i }).last().click()
  }

  async getSystemCardByName(name: string): Promise<Locator> {
    return this.page.getByText(name).first()
  }
}
