import AxeBuilder from '@axe-core/playwright'
import { expect, test } from './fixtures'

test('dashboard has no automatically detectable WCAG A/AA violations', async ({ page }) => {
  test.setTimeout(60_000)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /Review the exceptions/ })).toBeVisible()
  await expect(page.getByText('Loading your intake ledger…')).toBeHidden()
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
  expect(results.violations).toEqual([])
})
