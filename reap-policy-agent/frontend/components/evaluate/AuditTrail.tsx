'use client'
import { useEffect, useState } from 'react'
import type { CompiledRule, Decision } from '@/lib/types'
import { api } from '@/lib/api'
import { VerdictBadge } from '@/components/ui/VerdictBadge'
import { ActionBadge } from '@/components/ui/ActionBadge'

const PREDICATE_LABELS: Record<string, string> = {
  vendor_blocklist: 'Blocked Vendor',
  vendor_allowlist: 'Vendor Not on Approved List',
  amount_cap: 'Amount Cap Exceeded',
  amount_requires_receipt: 'Receipt Required',
  hotel_star_max: 'Hotel Star Limit',
  mcc_ban: 'Merchant Category Banned',
  per_diem_cap: 'Per Diem Cap Exceeded',
  category_pre_approval: 'Pre-Approval Required',
  requires_attendee_note: 'Attendee Note Required',
}

function ruleLabel(ruleId: string, ruleMap: Record<string, CompiledRule>): string {
  const rule = ruleMap[ruleId]
  if (!rule) return ruleId
  return PREDICATE_LABELS[rule.predicate] ?? rule.predicate.replace(/_/g, ' ')
}

export function AuditTrail({ decisions }: { decisions: Decision[] }) {
  const [ruleMap, setRuleMap] = useState<Record<string, CompiledRule>>({})
  const tenantId = process.env.NEXT_PUBLIC_TENANT_ID ?? 'meru-inc'

  useEffect(() => {
    api.getActivePolicy(tenantId)
      .then(policy => {
        const map: Record<string, CompiledRule> = {}
        for (const rule of policy.structured_rules) map[rule.rule_id] = rule
        setRuleMap(map)
      })
      .catch(() => {/* best-effort */})
  }, [tenantId])

  if (decisions.length === 0) return <p className="text-sm text-ink-muted">No audit entries found.</p>
  return (
    <ol className="relative border-l border-border space-y-6 pl-6">
      {decisions.map((d, i) => (
        <li key={d.decision_id} className="relative">
          <div className="absolute -left-[25px] w-3 h-3 rounded-full bg-brand-teal border-2 border-white" />
          <div className="bg-white rounded-lg border border-border px-4 py-3 space-y-2">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-xs text-ink-muted">#{decisions.length - i}</span>
              <VerdictBadge verdict={d.verdict} />
              <ActionBadge action={d.action_taken} />
              <span className="text-xs text-ink-muted ml-auto">{new Date(d.timestamp).toLocaleString()}</span>
            </div>
            {d.rule_path.length > 0 && (
              <p className="text-xs text-ink-muted">
                Rules: {d.rule_path.map(r => ruleLabel(r, ruleMap)).join(' · ')}
              </p>
            )}
            {d.agent_rationale && (
              <p className="text-xs text-ink">{d.agent_rationale}</p>
            )}
          </div>
        </li>
      ))}
    </ol>
  )
}
