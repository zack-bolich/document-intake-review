export type DocumentStatus = 'approved' | 'review' | 'duplicate' | 'failed' | 'processing'

export interface DocumentRecord {
  id: string
  filename: string
  document_type: string
  document_number: string | null
  vendor: string | null
  amount: string | null
  currency: string | null
  document_date: string | null
  confidence: string
  field_confidence: Record<string, number>
  status: DocumentStatus
  duplicate_of_id: string | null
  retry_count: number
  last_error: string | null
  created_at: string
  updated_at: string
  approved_at: string | null
}

export interface AuditEvent {
  id: string
  action: string
  actor: string
  details: Record<string, unknown>
  created_at: string
}

export interface DeadLetter {
  id: string
  filename: string
  error: string
  raw_text_excerpt: string
  retry_count: number
  created_at: string
  updated_at: string
}
