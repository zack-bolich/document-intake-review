import type { Page } from '@playwright/test'
import { expect, test } from './fixtures'

async function openDashboard(page: Page) {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /Review the exceptions/ })).toBeVisible()
  await expect(page.getByText('Loading your intake ledger…')).toBeHidden()
}

async function upload(page: Page, file: string) {
  await page.locator('input[type=file]').setInputFiles(file)
}

test.describe('document intake UI', () => {
  test('starts the Compose-served application and loads an empty dashboard', async ({ page }) => {
    await openDashboard(page)
    await expect(page.getByText('Local API connected')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Document records' })).toBeVisible()
  })

  test('uploads a valid PDF and shows extracted values and confidence', async ({ page, sample }) => {
    await openDashboard(page)
    await upload(page, sample('invoice_3001.pdf'))
    await expect(page.getByRole('status')).toContainText('processed as approved')
    const row = page.getByRole('row').filter({ hasText: 'invoice_3001.pdf' }).first()
    await expect(row.getByText('INV-3001')).toBeVisible()
    await expect(row.getByText('Northstar Office Supply')).toBeVisible()
    await expect(page.getByLabel(/% confidence/).first()).toBeVisible()
  })

  test('routes an incomplete PDF to review and exposes field confidence', async ({ page, sample }) => {
    await openDashboard(page)
    await upload(page, sample('invoice_needs_review.pdf'))
    await expect(page.getByRole('status')).toContainText('needs review')
    await page.getByRole('row').filter({ hasText: 'invoice_needs_review.pdf' }).first().click()
    await expect(page.getByLabel('Document review')).toBeVisible()
    await expect(page.getByText('0% extracted').first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'Approve record' })).toBeVisible()
  })

  test('saves reviewer corrections, approves the record, and preserves audit history', async ({ page }) => {
    await openDashboard(page)
    await page.getByRole('row').filter({ hasText: 'invoice_needs_review.pdf' }).first().click()
    const drawer = page.getByLabel('Document review')
    await drawer.locator('input[name=amount]').fill('87.20')
    await drawer.locator('input[name=document_date]').fill('2026-07-17')
    await drawer.getByRole('button', { name: 'Save corrections' }).click()
    await expect(drawer.getByText('corrected')).toBeVisible()
    await drawer.getByRole('button', { name: 'Approve record' }).click()
    await expect(drawer).toBeHidden()
    await expect(page.getByText('$87.20')).toBeVisible()
  })

  test('filters and searches records without changing persisted data', async ({ page }) => {
    await openDashboard(page)
    await page.getByRole('button', { name: /Approved/ }).click()
    await page.getByLabel('Search documents').fill('Northstar')
    await expect(page.getByText('Northstar Office Supply')).toBeVisible()
    await expect(page.getByText('Fictional Repair Works')).toBeHidden()
  })

  test('marks a repeated PDF as a duplicate', async ({ page, sample }) => {
    await openDashboard(page)
    await upload(page, sample('invoice_3001.pdf'))
    await expect(page.getByRole('status')).toContainText('processed as duplicate')
    await page.getByRole('button', { name: /Duplicate/ }).click()
    await expect(page.getByRole('row').filter({ hasText: 'invoice_3001.pdf' }).first()).toBeVisible()
  })

  test('shows an unsupported-file error without creating a record', async ({ page }) => {
    await openDashboard(page)
    await page.locator('input[type=file]').setInputFiles({
      name: 'malware.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('safe fixture'),
    })
    await expect(page.getByRole('status')).toContainText('Supported formats: PDF, TXT, JSON')
  })

  test('downloads approved records as CSV', async ({ page }) => {
    await openDashboard(page)
    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Download CSV' }).click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toBe('approved-records.csv')
  })
})
