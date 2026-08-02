import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertCircle, ChevronRight, FileText, Inbox, LoaderCircle, RefreshCw, Search, ShieldCheck,
} from 'lucide-react'
import { api } from './api'
import { dateTime, money } from './format'
import { statusMeta } from './statusMeta'
import { Confidence } from './components/Confidence'
import { ExportPanel } from './components/ExportPanel'
import { ReviewPanel } from './components/ReviewPanel'
import { StatusBadge } from './components/StatusBadge'
import { UploadPanel } from './components/UploadPanel'
import type { DeadLetter, DocumentRecord, DocumentStatus } from './types'

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
