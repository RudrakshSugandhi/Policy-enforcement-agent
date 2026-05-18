import type { CompiledPolicy } from '@/lib/types'
import { PolicyRulesTable } from './PolicyRulesTable'

export function CompiledPolicyPreview({ policy }: { policy: CompiledPolicy }) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4 text-sm">
        <div className="bg-white rounded-lg border border-border px-4 py-3">
          <p className="text-xs text-ink-muted mb-1">Version</p>
          <p className="font-semibold text-ink">v{policy.version}</p>
        </div>
        <div className="bg-white rounded-lg border border-border px-4 py-3">
          <p className="text-xs text-ink-muted mb-1">Status</p>
          <span className="inline-block px-2 py-0.5 rounded-full text-xs font-semibold bg-yellow-100 text-yellow-800 border border-yellow-200 capitalize">
            {policy.status}
          </span>
        </div>
        <div className="bg-white rounded-lg border border-border px-4 py-3">
          <p className="text-xs text-ink-muted mb-1">Rules compiled</p>
          <p className="font-semibold text-ink">{policy.structured_rules.length} structured</p>
        </div>
      </div>

      <section>
        <h3 className="text-sm font-semibold text-ink mb-3">Structured Rules</h3>
        <PolicyRulesTable rules={policy.structured_rules} />
      </section>

      {policy.natural_language_references.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-ink mb-3">Natural Language References</h3>
          <ul className="space-y-2">
            {policy.natural_language_references.map(ref => (
              <li key={ref.ref_id} className="bg-white rounded-lg border border-border px-4 py-3 text-sm">
                <p className="text-ink">{ref.clause_text}</p>
                {ref.keywords.length > 0 && (
                  <p className="mt-1 text-xs text-ink-muted">Keywords: {ref.keywords.join(', ')}</p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {policy.unsupported_clauses.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-ink mb-3">Unsupported Clauses</h3>
          <ul className="space-y-2">
            {policy.unsupported_clauses.map((c, i) => (
              <li key={i} className="bg-red-50 rounded-lg border border-red-200 px-4 py-3 text-sm">
                <p className="text-ink">{c.clause_text}</p>
                <p className="mt-1 text-xs text-red-600">Reason: {c.reason}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
