export function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = pct === 100 ? 'bg-green-500' : pct >= 80 ? 'bg-yellow-400' : 'bg-orange-400'
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-muted-bg rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-ink-muted w-8 text-right">{pct}%</span>
    </div>
  )
}
