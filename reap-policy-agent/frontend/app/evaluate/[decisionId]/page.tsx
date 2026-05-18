'use client'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { Decision } from '@/lib/types'
import { DecisionPanel } from '@/components/evaluate/DecisionPanel'
import { AuditTrail } from '@/components/evaluate/AuditTrail'
import { Loader2 } from 'lucide-react'

export default function DecisionDetailPage({ params }: { params: { decisionId: string } }) {
  const [decisions, setDecisions] = useState<Decision[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getDecisions(params.decisionId)
      .then(setDecisions)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [params.decisionId])

  const latest = decisions[decisions.length - 1]

  if (loading) return (
    <div className="flex items-center gap-2 text-ink-muted text-sm py-16 justify-center">
      <Loader2 size={16} className="animate-spin" /> Loading decision...
    </div>
  )

  if (error) return (
    <div className="max-w-3xl mx-auto bg-red-50 border border-red-200 rounded-lg px-5 py-4 text-sm text-red-700">{error}</div>
  )

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Decision Detail</h1>
        <p className="text-xs text-ink-muted mt-1 font-mono">{params.decisionId}</p>
      </div>
      {latest && (
        <div className="bg-white rounded-xl border border-border p-6 space-y-4">
          <h2 className="text-sm font-semibold text-ink">Latest Decision</h2>
          <DecisionPanel decision={latest} />
        </div>
      )}
      <div className="bg-white rounded-xl border border-border p-6 space-y-4">
        <h2 className="text-sm font-semibold text-ink">Audit Trail</h2>
        <AuditTrail decisions={decisions} />
      </div>
    </div>
  )
}
