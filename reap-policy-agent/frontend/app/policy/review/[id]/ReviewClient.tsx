'use client'
import { useEffect, useState } from 'react'
import type { CompiledPolicy } from '@/lib/types'
import { api } from '@/lib/api'
import { CompiledPolicyPreview } from '@/components/policy/CompiledPolicyPreview'
import { PolicyApproveReject } from '@/components/policy/PolicyApproveReject'
import { Loader2 } from 'lucide-react'

export function ReviewClient({ policyId }: { policyId: string }) {
  const [policy, setPolicy] = useState<CompiledPolicy | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getPolicy(policyId)
      .then(setPolicy)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Could not load policy.')
      })
  }, [policyId])

  if (error) return (
    <div className="bg-red-50 border border-red-200 rounded-lg px-5 py-4 text-sm text-red-700">{error}</div>
  )

  if (!policy) return (
    <div className="flex items-center gap-2 text-ink-muted text-sm py-12 justify-center">
      <Loader2 size={16} className="animate-spin" /> Loading compiled policy...
    </div>
  )

  if (policy.status === 'active') return (
    <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-5 py-4 text-sm text-yellow-800">
      This policy is already <strong>active</strong>. Go to{' '}
      <a href="/evaluate" className="underline text-brand-teal">Evaluate</a> to test transactions against it.
    </div>
  )

  if (policy.status === 'deprecated') return (
    <div className="bg-muted-bg border border-border rounded-lg px-5 py-4 text-sm text-ink-muted">
      This policy version has been <strong>deprecated</strong> and replaced by a newer active version.{' '}
      <a href="/policy/create" className="underline text-brand-teal">Create a new policy</a> to start fresh.
    </div>
  )

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl border border-border p-6">
        <CompiledPolicyPreview policy={policy} />
      </div>
      <div className="bg-white rounded-xl border border-border p-6">
        <h2 className="text-sm font-semibold text-ink mb-4">Decision</h2>
        <PolicyApproveReject policyId={String(policy.policy_id)} />
      </div>
    </div>
  )
}
