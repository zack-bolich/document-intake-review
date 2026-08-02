import { statusMeta } from '../statusMeta'
import type { DocumentStatus } from '../types'

export function StatusBadge({ status }: { status: DocumentStatus }) {
  const { label, icon: Icon } = statusMeta[status]
  return <span className={`status status-${status}`}><Icon size={14} />{label}</span>
}
