import type { Verdict } from '@/lib/types'

const config: Record<Verdict, { label: string; className: string }> = {
  pass_through:   { label: 'Pass',           className: 'bg-green-100 text-green-800 border-green-200' },
  needs_evidence: { label: 'Needs Evidence', className: 'bg-yellow-100 text-yellow-800 border-yellow-200' },
  needs_judgment: { label: 'Needs Judgment', className: 'bg-orange-100 text-orange-800 border-orange-200' },
  fail:           { label: 'Fail',           className: 'bg-red-100 text-red-800 border-red-200' },
  abstain:        { label: 'Abstain',        className: 'bg-muted-bg text-ink-muted border-border' },
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const { label, className } = config[verdict] ?? config.abstain
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${className}`}>
      {label}
    </span>
  )
}
