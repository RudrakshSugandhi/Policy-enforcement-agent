import type { ActionType } from '@/lib/types'

const config: Record<ActionType, { label: string; className: string }> = {
  pass_through:     { label: 'Pass Through',     className: 'bg-green-50 text-green-700 border-green-200' },
  block:            { label: 'Block',            className: 'bg-red-50 text-red-700 border-red-200' },
  flag:             { label: 'Flag for Review',  className: 'bg-orange-50 text-orange-700 border-orange-200' },
  request_evidence: { label: 'Request Evidence', className: 'bg-yellow-50 text-yellow-700 border-yellow-200' },
  escalate:         { label: 'Escalate',         className: 'bg-purple-50 text-purple-700 border-purple-200' },
  propose_clawback: { label: 'Propose Clawback', className: 'bg-red-50 text-red-800 border-red-300' },
}

export function ActionBadge({ action }: { action: ActionType }) {
  const { label, className } = config[action] ?? config.flag
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${className}`}>
      {label}
    </span>
  )
}
