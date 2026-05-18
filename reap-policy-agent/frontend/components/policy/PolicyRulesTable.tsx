import type { CompiledRule } from '@/lib/types'

export function PolicyRulesTable({ rules }: { rules: CompiledRule[] }) {
  if (rules.length === 0) return <p className="text-sm text-ink-muted">No structured rules compiled.</p>
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead className="bg-muted-bg text-xs text-ink-muted uppercase tracking-wide">
          <tr>
            <th className="px-4 py-3 text-left">Predicate</th>
            <th className="px-4 py-3 text-left">Parameters</th>
            <th className="px-4 py-3 text-left">Action</th>
            <th className="px-4 py-3 text-left">Source clause</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border bg-white">
          {rules.map(rule => (
            <tr key={rule.rule_id} className="hover:bg-muted-bg">
              <td className="px-4 py-3 font-mono text-xs text-brand-teal whitespace-nowrap">{rule.predicate}</td>
              <td className="px-4 py-3 font-mono text-xs text-ink-muted max-w-xs truncate">
                {JSON.stringify(rule.parameters)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap">
                <span className="text-xs font-medium text-ink">{rule.action_on_violation}</span>
              </td>
              <td className="px-4 py-3 text-xs text-ink-muted max-w-sm">{rule.source_clause}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
