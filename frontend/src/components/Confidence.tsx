export function Confidence({ value }: { value: string | number }) {
  const percent = Math.round(Number(value) * 100)
  const tone = percent >= 85 ? 'high' : percent >= 65 ? 'medium' : 'low'
  return (
    <div className="confidence" aria-label={`${percent}% confidence`}>
      <div className="confidence-track"><span className={tone} style={{ width: `${percent}%` }} /></div>
      <strong>{percent}%</strong>
    </div>
  )
}
