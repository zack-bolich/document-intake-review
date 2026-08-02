import { useEffect, useState } from 'react'
import { AlertCircle, Check, History, X } from 'lucide-react'
import { api } from '../api'
import { dateTime } from '../format'
import { Confidence } from './Confidence'
import { StatusBadge } from './StatusBadge'
import type { AuditEvent, DocumentRecord } from '../types'

export function ReviewPanel({ record, onClose, onSaved }: {
  record: DocumentRecord; onClose: () => void; onSaved: (record: DocumentRecord) => void
}) {
  const [form, setForm] = useState({
    vendor: record.vendor ?? '', document_number: record.document_number ?? '',
    amount: record.amount ?? '', currency: record.currency ?? 'USD', document_date: record.document_date ?? '',
  })
  const [audit, setAudit] = useState<AuditEvent[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { void api.audit(record.id).then(setAudit).catch(() => setAudit([])) }, [record.id])

  const save = async (approve = false) => {
    setBusy(true); setError(null)
    try {
      let updated = await api.correct(record.id, { ...form, amount: form.amount || null, document_date: form.document_date || null, actor: 'Dashboard reviewer' })
      if (approve) updated = await api.approve(record.id, 'Dashboard reviewer')
      onSaved(updated)
      if (approve) onClose()
      else setAudit(await api.audit(record.id))
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not save changes') }
    finally { setBusy(false) }
  }

  return (
    <div className="drawer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <aside className="drawer" aria-label="Document review">
        <header className="drawer-header">
          <div><span className="eyebrow">Document review</span><h2>{record.filename}</h2></div>
          <button className="icon-button" onClick={onClose} aria-label="Close review"><X size={20} /></button>
        </header>
        <div className="drawer-content">
          <div className="review-summary"><StatusBadge status={record.status} /><Confidence value={record.confidence} /></div>
          <div className="field-grid">
            {([
              ['vendor', 'Vendor'], ['document_number', 'Document number'], ['amount', 'Amount'],
              ['currency', 'Currency'], ['document_date', 'Document date'],
            ] as const).map(([name, label]) => {
              const confidence = record.field_confidence[name] ?? 0
              return <label key={name} className={confidence < .85 ? 'uncertain' : ''}>
                <span>{label}<small>{Math.round(confidence * 100)}% extracted</small></span>
                <input name={name} type={name === 'amount' ? 'number' : name === 'document_date' ? 'date' : 'text'} step="0.01" value={form[name]} onChange={(event) => setForm({ ...form, [name]: event.target.value })} />
              </label>
            })}
          </div>
          {error && <div className="error-message"><AlertCircle size={16} />{error}</div>}
          <div className="drawer-actions">
            <button className="button secondary" disabled={busy} onClick={() => void save(false)}>Save corrections</button>
            {record.status === 'review' && <button className="button primary" disabled={busy} onClick={() => void save(true)}><Check size={17} />Approve record</button>}
          </div>
          <section className="audit-section">
            <div className="section-heading"><div><span className="eyebrow">Traceability</span><h3>Audit history</h3></div><History size={19} /></div>
            <ol className="timeline">
              {audit.map((event) => <li key={event.id}><span className="timeline-dot" /><div><strong>{event.action.replaceAll('_', ' ')}</strong><p>{event.actor} · {dateTime(event.created_at)}</p></div></li>)}
            </ol>
          </section>
        </div>
      </aside>
    </div>
  )
}
