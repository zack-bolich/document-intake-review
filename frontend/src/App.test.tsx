import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const record = {
  id: 'doc-1', filename: 'invoice_review.pdf', document_type: 'invoice', document_number: 'INV-1',
  vendor: 'Fictional Repair Works', amount: null, currency: 'USD', document_date: null,
  confidence: '0.6100', field_confidence: { document_number: .98, vendor: .98, amount: 0, currency: .75, document_type: .95, document_date: 0 },
  status: 'review', duplicate_of_id: null, retry_count: 0, last_error: null,
  created_at: '2026-07-21T17:16:22Z', updated_at: '2026-07-21T17:16:22Z', approved_at: null,
}

describe('review dashboard', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async (input: string | URL) => {
      const url = String(input)
      if (url.endsWith('/dead-letters')) return new Response(JSON.stringify([]), { status: 200 })
      if (url.endsWith('/audit')) return new Response(JSON.stringify([{ id: 'a1', action: 'ingested', actor: 'system', details: {}, created_at: record.created_at }]), { status: 200 })
      return new Response(JSON.stringify([record]), { status: 200 })
    }))
  })
  afterEach(() => vi.unstubAllGlobals())

  it('shows records, confidence, and opens review details', async () => {
    render(<App />)
    expect(await screen.findByText('Fictional Repair Works')).toBeInTheDocument()
    expect(screen.getAllByText('61%').length).toBeGreaterThan(0)
    await userEvent.click(screen.getByText('Fictional Repair Works'))
    expect(await screen.findByLabelText('Document review')).toBeInTheDocument()
    expect(screen.getByDisplayValue('INV-1')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('ingested')).toBeInTheDocument())
  })

  it('filters the review queue', async () => {
    render(<App />)
    await screen.findByText('Fictional Repair Works')
    await userEvent.click(screen.getAllByRole('button', { name: /Needs review/ })[0])
    expect(screen.getByText('INV-1')).toBeInTheDocument()
  })
})
