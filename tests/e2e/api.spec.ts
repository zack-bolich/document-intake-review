import { expect, test } from './fixtures'
import { readFileSync } from 'node:fs'

test.describe('document intake API', () => {
  test('publishes health and the documented OpenAPI contract', async ({ request, apiOrigin }) => {
    await expect.poll(async () => (await request.get(`${apiOrigin}/health`)).status()).toBe(200)
    const contract = await request.get(`${apiOrigin}/openapi.json`)
    expect(contract.ok()).toBeTruthy()
    expect(Object.keys((await contract.json()).paths)).toContain('/api/v1/documents')
  })

  test('returns structured extraction data for a valid PDF', async ({ request, apiBaseURL, sample }) => {
    const response = await request.post(`${apiBaseURL}/documents`, {
      multipart: { file: { name: 'receipt-api.pdf', mimeType: 'application/pdf', buffer: readFileSync(sample('receipt_2002.pdf')) } },
    })
    expect(response.status()).toBe(201)
    const record = await response.json()
    expect(record).toMatchObject({ status: 'approved', document_number: 'RCP-2002', vendor: 'Synthetic Corner Cafe' })
    expect(Number(record.field_confidence.amount)).toBeGreaterThan(.9)
  })

  test('corrects and approves a review record with an auditable actor', async ({ request, apiBaseURL }) => {
    const created = await request.post(`${apiBaseURL}/documents`, { multipart: {
      file: { name: 'api-review.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify({ doc_type: 'invoice', document_number: 'API-REVIEW-1', vendor: 'Sanitized API Vendor' })) },
    } })
    const id = (await created.json()).id
    const correction = await request.patch(`${apiBaseURL}/documents/${id}`, { data: { amount: '48.25', currency: 'usd', document_date: '2026-07-18', actor: 'playwright-api-reviewer' } })
    expect(correction.ok()).toBeTruthy()
    expect((await correction.json()).currency).toBe('USD')
    const approval = await request.post(`${apiBaseURL}/documents/${id}/approve`, { data: { actor: 'playwright-api-reviewer' } })
    expect((await approval.json()).status).toBe('approved')
    const audit = await (await request.get(`${apiBaseURL}/documents/${id}/audit`)).json()
    expect(audit.map((event: { action: string }) => event.action)).toEqual(['ingested', 'corrected', 'approved'])
    expect(audit.at(-1).actor).toBe('playwright-api-reviewer')
  })

  test('rejects unsupported upload formats', async ({ request, apiBaseURL }) => {
    const response = await request.post(`${apiBaseURL}/documents`, { multipart: {
      file: { name: 'unsafe.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('sanitized') },
    } })
    expect(response.status()).toBe(415)
    expect(await response.json()).toEqual({ detail: 'Supported formats: PDF, TXT, JSON' })
  })

  test('rejects approval when required fields are missing', async ({ request, apiBaseURL }) => {
    const created = await request.post(`${apiBaseURL}/documents`, { multipart: {
      file: { name: 'incomplete-api.txt', mimeType: 'text/plain', buffer: Buffer.from('INVOICE\nVendor: Missing Fields LLC\nInvoice Number: API-INCOMPLETE-1') },
    } })
    const response = await request.post(`${apiBaseURL}/documents/${(await created.json()).id}/approve`, { data: { actor: 'negative-test' } })
    expect(response.status()).toBe(422)
    expect((await response.json()).detail.missing_fields).toEqual(expect.arrayContaining(['amount', 'document_date']))
  })

  test('returns validation and not-found errors without side effects', async ({ request, apiBaseURL }) => {
    const created = await request.post(`${apiBaseURL}/documents`, { multipart: {
      file: { name: 'validation-target.txt', mimeType: 'text/plain', buffer: Buffer.from('INVOICE\nVendor: Validation Vendor\nInvoice Number: API-VALIDATION-1') },
    } })
    expect(created.status()).toBe(201)
    const invalid = await request.patch(`${apiBaseURL}/documents/${(await created.json()).id}`, { data: { amount: -1 } })
    expect(invalid.status()).toBe(422)
    const missing = await request.get(`${apiBaseURL}/documents/missing-id`)
    expect(missing.status()).toBe(404)
    expect(await missing.json()).toEqual({ detail: 'Document not found' })
  })
})
