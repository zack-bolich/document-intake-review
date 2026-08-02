export const money = (amount: string | null, currency: string | null) => amount
  ? new Intl.NumberFormat('en-US', { style: 'currency', currency: currency ?? 'USD' }).format(Number(amount))
  : '—'

export const dateTime = (value: string) => new Intl.DateTimeFormat('en-US', {
  month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
}).format(new Date(value))
