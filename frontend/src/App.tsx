import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertCircle, Check, CheckCircle2, ChevronRight, Clock3, Copy, Download, FileText,
  History, Inbox, LoaderCircle, RefreshCw, Search, ShieldCheck, Table2, UploadCloud, X,
} from 'lucide-react'
import { api } from './api'
import type { AuditEvent, DeadLetter, DocumentRecord, DocumentStatus } from './types'

const statusMeta: Record<DocumentStatus, { label: string; icon: typeof CheckCircle2 }> = {
  approved: { label: 'Approved', icon: CheckCircle2 },
  review: { label: 'Needs review', icon: Clock3 },
  duplicate: { label: 'Duplicate', icon: Copy },
  failed: { label: 'Failed', icon: AlertCircle },
  processing: { label: 'Processing', icon: LoaderCircle },
}

const money = (amount: string | null, currency: string | null) => amount
  ? new Intl.NumberFormat('en-US', { style: 'currency', currency: currency ?? 'USD' }).format(Number(amount))
  : '—'

const dateTime = (value: string) => new Intl.DateTimeFormat('en-US', {
  month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
}).format(new Date(value))

function StatusBadge({ status }: { status: DocumentStatus }) {
  const { label, icon: Icon } = statusMeta[status]
  return <span className={`status status-${status}`}><Icon size={14} />{label}</span>
}

function Confidence({ value }: { value: string | number }) {
  const percent = Math.round(Number(value) * 100)
  const tone = percent >= 85 ? 'high' : percent >= 65 ? 'medium' : 'low'
  return (
    <div className="confidence" aria-label={`${percent}% confidence`}>
      <div className="confidence-track"><span className={tone} style={{ width: `${percent}%` }} /></div>
      <strong>{percent}%</strong>
    </div>
  )
}

function UploadPanel({ onUploaded }: { onUploaded: (record: DocumentRecord) => void }) {
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const upload = async (file?: File) => {
    if (!file) return
    setBusy(true); setMessage(null)
    try {
      const record = await api.upload(file)
      onUploaded(record)
      setMessage(`${file.name} processed as ${statusMeta[record.status].label.toLowerCase()}.`)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Upload failed')
    } finally { setBusy(false) }
  }

  return (
    <section className="upload-card">
      <div className="section-heading">
        <div><span className="eyebrow">New intake</span><h2>Process a document</h2></div>
        <span className="format-note">PDF · TXT · JSON</span>
      </div>
      <label
        className={`dropzone ${dragging ? 'dragging' : ''}`}
        onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => { event.preventDefault(); setDragging(false); void upload(event.dataTransfer.files[0]) }}
      >
        <input type="file" accept=".pdf,.txt,.json" onChange={(event) => void upload(event.target.files?.[0])} />
        {busy ? <LoaderCircle className="spin" size={30} /> : <UploadCloud size={30} />}
        <div><strong>{busy ? 'Extracting fields…' : 'Drop a document here'}</strong><span>or click to browse synthetic samples</span></div>
      </label>
      {message && <p className="upload-message" role="status">{message}</p>}
    </section>
  )
}

function ExportPanel({ approvedCount }: { approvedCount: number }) {
  const [busy, setBusy] = useState<'csv' | 'sheets' | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const downloadCsv = async () => {
    setBusy('csv'); setMessage(null)
    try {
      await api.downloadApprovedCsv()
      setMessage(`Downloaded ${approvedCount} approved record${approvedCount === 1 ? '' : 's'}.`)
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Export failed') }
    finally { setBusy(null) }
  }

  const exportSheets = async () => {
    setBusy('sheets'); setMessage(null)
    try {
      const result = await api.exportGoogleSheets()
      setMessage(result.exported_count
        ? `Added ${result.exported_count} record${result.exported_count === 1 ? '' : 's'} to Google Sheets.`
        : 'Google Sheets is already up to date.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Google Sheets export failed')
    } finally { setBusy(null) }
  }

  return (
    <section className="export-card">
      <div className="export-copy"><span className="eyebrow">Approved output</span><h2>Move clean records downstream</h2><p>Download a portable CSV now, or append new approvals to a configured Google Sheet.</p></div>
      <div className="export-actions">
        <button className="button secondary" disabled={!approvedCount || busy !== null} onClick={() => void downloadCsv()}>{busy === 'csv' ? <LoaderCircle className="spin" size={16} /> : <Download size={16} />}Download CSV</button>
        <button className="button primary" disabled={!approvedCount || busy !== null} onClick={() => void exportSheets()}>{busy === 'sheets' ? <LoaderCircle className="spin" size={16} /> : <Table2 size={16} />}Export to Sheets</button>
        {message && <span className="export-message" role="status">{message}</span>}
      </div>
    </section>
  )
}

function ReviewPanel({ record, onClose, onSaved }: {
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

export default function App() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([])
  const [deadLetters, setDeadLetters] = useState<DeadLetter[]>([])
  const [activeFilter, setActiveFilter] = useState<'all' | DocumentStatus>('all')
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<DocumentRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [records, failed] = await Promise.all([api.listDocuments(), api.listDeadLetters()])
      setDocuments(records); setDeadLetters(failed)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not connect to the API') }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { void Promise.resolve().then(load) }, [load])

  const visible = useMemo(() => documents.filter((record) => {
    const matchesFilter = activeFilter === 'all' || record.status === activeFilter
    const needle = query.toLowerCase()
    return matchesFilter && (!needle || [record.filename, record.vendor, record.document_number].some((value) => value?.toLowerCase().includes(needle)))
  }), [documents, activeFilter, query])

  const replace = (record: DocumentRecord) => setDocuments((current) => [record, ...current.filter((item) => item.id !== record.id)])
  const counts = {
    all: documents.length, review: documents.filter((d) => d.status === 'review').length,
    approved: documents.filter((d) => d.status === 'approved').length,
    duplicate: documents.filter((d) => d.status === 'duplicate').length, failed: deadLetters.length,
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/"><span className="brand-mark"><FileText size={20} /></span><span>Ledgerline<small>Document operations</small></span></a>
        <div className="system-status"><span className="pulse" />Local API connected</div>
      </header>
      <main>
        <section className="hero">
          <div><span className="eyebrow">Document intelligence workspace</span><h1>Review the exceptions.<br /><em>Trust the trail.</em></h1><p>Turn incoming invoices and receipts into approved, auditable records—with human judgment exactly where it matters.</p></div>
          <div className="hero-seal"><ShieldCheck size={30} /><strong>{counts.approved}</strong><span>approved records</span></div>
        </section>

        <div className="dashboard-grid">
          <UploadPanel onUploaded={replace} />
          <section className="metrics-card">
            <div className="section-heading"><div><span className="eyebrow">At a glance</span><h2>Processing health</h2></div><button className="icon-button" onClick={() => void load()} aria-label="Refresh"><RefreshCw size={18} /></button></div>
            <div className="metrics">
              <div><strong>{counts.review}</strong><span>Need review</span></div><div><strong>{counts.approved}</strong><span>Approved</span></div><div><strong>{counts.duplicate}</strong><span>Duplicates</span></div><div><strong>{counts.failed}</strong><span>Failed</span></div>
            </div>
          </section>
        </div>

        <ExportPanel approvedCount={counts.approved} />

        <section className="records-card">
          <div className="records-header">
            <div><span className="eyebrow">Intake ledger</span><h2>Document records</h2></div>
            <label className="search"><Search size={17} /><input aria-label="Search documents" placeholder="Search vendor or reference…" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
          </div>
          <nav className="filters" aria-label="Record filters">
            {(['all', 'review', 'approved', 'duplicate'] as const).map((filter) => <button key={filter} className={activeFilter === filter ? 'active' : ''} onClick={() => setActiveFilter(filter)}>{filter === 'all' ? 'All records' : statusMeta[filter].label}<span>{counts[filter]}</span></button>)}
          </nav>
          {error && <div className="empty-state"><AlertCircle /><h3>API unavailable</h3><p>{error}</p><button className="button secondary" onClick={() => void load()}>Try again</button></div>}
          {!error && loading && <div className="empty-state"><LoaderCircle className="spin" /><p>Loading your intake ledger…</p></div>}
          {!error && !loading && visible.length === 0 && <div className="empty-state"><Inbox /><h3>No matching records</h3><p>Upload a sample document or choose another filter.</p></div>}
          {!error && !loading && visible.length > 0 && <div className="table-wrap"><table>
            <thead><tr><th>Document</th><th>Vendor</th><th>Amount</th><th>Confidence</th><th>Status</th><th aria-label="Actions" /></tr></thead>
            <tbody>{visible.map((record) => <tr key={record.id} onClick={() => setSelected(record)}>
              <td><div className="document-cell"><span className="file-icon"><FileText size={18} /></span><div><strong>{record.document_number ?? 'No reference'}</strong><span>{record.filename} · {dateTime(record.created_at)}</span></div></div></td>
              <td>{record.vendor ?? <span className="missing">Missing vendor</span>}</td><td>{money(record.amount, record.currency)}</td><td><Confidence value={record.confidence} /></td><td><StatusBadge status={record.status} /></td><td><button className="row-action" aria-label={`Review ${record.filename}`}><ChevronRight size={18} /></button></td>
            </tr>)}</tbody>
          </table></div>}
        </section>

        {deadLetters.length > 0 && <section className="failed-card"><div className="section-heading"><div><span className="eyebrow">Dead-letter queue</span><h2>Failed extractions</h2></div><AlertCircle size={20} /></div>{deadLetters.map((dead) => <div className="failed-row" key={dead.id}><div><strong>{dead.filename}</strong><span>{dead.error} · {dead.retry_count} retries</span></div><button className="button secondary" onClick={() => void api.retry(dead.id).then(replace).then(load).catch(load)}><RefreshCw size={15} />Retry</button></div>)}</section>}
      </main>
      <footer><span>Ledgerline portfolio build</span><span>Deterministic extraction · Human review · Full audit</span></footer>
      {selected && <ReviewPanel record={selected} onClose={() => setSelected(null)} onSaved={(record) => { replace(record); setSelected(record) }} />}
    </div>
  )
}
