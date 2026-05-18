'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { CheckCircle, XCircle, Loader2 } from 'lucide-react'

export function PolicyApproveReject({ policyId }: { policyId: string }) {
  const [loading, setLoading] = useState<'approve' | 'reject' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const router = useRouter()

  async function approve() {
    setLoading('approve')
    setError(null)
    try {
      await api.approvePolicy(policyId, 'reviewer')
      router.push('/evaluate')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Approval failed')
      setLoading(null)
    }
  }

  function reject() {
    setLoading('reject')
    router.push('/policy/create')
  }

  return (
    <div className="space-y-4">
      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-4 py-2">{error}</p>
      )}
      <div className="flex gap-3">
        <button
          onClick={approve}
          disabled={loading !== null}
          className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-brand-teal text-white text-sm font-semibold hover:bg-brand-teal-dark disabled:opacity-60 transition-colors"
        >
          {loading === 'approve' ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
          Approve policy
        </button>
        <button
          onClick={reject}
          disabled={loading !== null}
          className="flex items-center gap-2 px-6 py-2.5 rounded-lg border border-red-300 text-red-600 text-sm font-semibold hover:bg-red-50 disabled:opacity-60 transition-colors"
        >
          <XCircle size={14} />
          Reject
        </button>
      </div>
    </div>
  )
}
