import { AlertCircle, CheckCircle2, Clock3, Copy, LoaderCircle } from 'lucide-react'
import type { DocumentStatus } from './types'

export const statusMeta: Record<DocumentStatus, { label: string; icon: typeof CheckCircle2 }> = {
  approved: { label: 'Approved', icon: CheckCircle2 },
  review: { label: 'Needs review', icon: Clock3 },
  duplicate: { label: 'Duplicate', icon: Copy },
  failed: { label: 'Failed', icon: AlertCircle },
  processing: { label: 'Processing', icon: LoaderCircle },
}
