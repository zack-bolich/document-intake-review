import { useState } from 'react'
import { LoaderCircle, UploadCloud } from 'lucide-react'
import { api } from '../api'
import { statusMeta } from '../statusMeta'
import type { DocumentRecord } from '../types'

export function UploadPanel({ onUploaded }: { onUploaded: (record: DocumentRecord) => void }) {
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
