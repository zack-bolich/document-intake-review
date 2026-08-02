import { useState } from 'react'
import { Download, LoaderCircle, Table2 } from 'lucide-react'
import { api } from '../api'

export function ExportPanel({ approvedCount }: { approvedCount: number }) {
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
