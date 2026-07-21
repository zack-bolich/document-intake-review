import type { AuditEvent, DeadLetter, DocumentRecord } from './types'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init)
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }))
    const detail = typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail)
    throw new Error(detail || 'Request failed')
  }
  return response.json() as Promise<T>
}

export const api = {
  listDocuments: () => request<DocumentRecord[]>('/documents'),
  listDeadLetters: () => request<DeadLetter[]>('/dead-letters'),
  upload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<DocumentRecord>('/documents', { method: 'POST', body: form })
  },
  correct: (id: string, changes: Record<string, unknown>) =>
    request<DocumentRecord>(`/documents/${id}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(changes),
    }),
  approve: (id: string, actor: string) =>
    request<DocumentRecord>(`/documents/${id}/approve`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ actor }),
    }),
  audit: (id: string) => request<AuditEvent[]>(`/documents/${id}/audit`),
  retry: (id: string) => request<DocumentRecord>(`/dead-letters/${id}/retry`, { method: 'POST' }),
}
