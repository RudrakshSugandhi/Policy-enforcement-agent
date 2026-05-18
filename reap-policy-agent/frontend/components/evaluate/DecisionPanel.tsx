'use client'
import { useEffect, useState } from 'react'
import type { CompiledRule, Decision } from '@/lib/types'
import { api } from '@/lib/api'
import { VerdictBadge } from '@/components/ui/VerdictBadge'
import { ActionBadge } from '@/components/ui/ActionBadge'
import { ConfidenceBar } from '@/components/ui/ConfidenceBar'
import { ReceiptSubmitForm } from './ReceiptSubmitForm'
import { Bot } from 'lucide-react'

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

function RuleCard({ ruleId, ruleMap }: { ruleId: string; ruleMap: Record<string, CompiledRule> }) {
  const rule = ruleMap[ruleId]
  if (!rule) {
    return (
      <li className="rounded-lg border border-border bg-muted-bg px-4 py-3">
        <p className="text-xs font-mono text-ink-muted">{ruleId}</p>
      </li>
    )
  }
  const label = PREDICATE_LABELS[rule.predicate] ?? rule.predicate.replace(/_/g, ' ')
  return (
    <li className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 space-y-1">
      <p className="text-sm font-semibold text-red-800">{label}</p>
      <p className="text-xs text-red-700 leading-relaxed">{rule.source_clause}</p>
    </li>
  )
}

export function DecisionPanel({ decision: initialDecision }: { decision: Decision }) {
  const [ruleMap, setRuleMap] = useState<Record<string, CompiledRule>>({})
  const [decision, setDecision] = useState<Decision>(initialDecision)
  const tenantId = process.env.NEXT_PUBLIC_TENANT_ID ?? 'meru-inc'

  useEffect(() => { setDecision(initialDecision) }, [initialDecision])

  useEffect(() => {
    api.getActivePolicy(tenantId)
      .then(policy => {
        const map: Record<string, CompiledRule> = {}
        for (const rule of policy.structured_rules) map[rule.rule_id] = rule
        setRuleMap(map)
      })
      .catch(() => {/* policy lookup best-effort */})
  }, [tenantId])

  return (
    <div className="bg-white rounded-lg border border-border divide-y divide-border">
      <div className="px-5 py-4 flex items-center gap-4 flex-wrap">
        <VerdictBadge verdict={decision.verdict} />
        <ActionBadge action={decision.action_taken} />
        {decision.agent_used && (
          <span className="flex items-center gap-1 text-xs text-purple-700 bg-purple-50 border border-purple-200 px-2 py-0.5 rounded-full font-medium">
            <Bot size={11} /> LLM judgment
          </span>
        )}
        <span className="text-xs text-ink-muted ml-auto">Policy v{decision.policy_version}</span>
      </div>

      <div className="px-5 py-4">
        <p className="text-xs text-ink-muted mb-2">Confidence</p>
        <ConfidenceBar value={decision.confidence} />
      </div>

      {decision.rule_path.length > 0 && (
        <div className="px-5 py-4">
          <p className="text-xs text-ink-muted mb-2">Rules violated</p>
          <ul className="space-y-2">
            {decision.rule_path.map(r => (
              <RuleCard key={r} ruleId={r} ruleMap={ruleMap} />
            ))}
          </ul>
        </div>
      )}

      {decision.agent_rationale && (
        <div className="px-5 py-4">
          <p className="text-xs text-ink-muted mb-2">LLM rationale</p>
          <p className="text-sm text-ink leading-relaxed bg-purple-50 border border-purple-100 rounded-lg px-4 py-3">
            {decision.agent_rationale}
          </p>
        </div>
      )}

      {decision.verdict === 'needs_evidence' && (
        <div className="px-5 py-4">
          <p className="text-xs font-semibold text-ink mb-3">Submit Receipt</p>
          <ReceiptSubmitForm
            transactionId={String(decision.transaction_id)}
            onNewDecision={setDecision}
          />
        </div>
      )}
    </div>
  )
}
