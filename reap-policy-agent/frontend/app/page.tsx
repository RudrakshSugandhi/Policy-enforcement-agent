'use client'
import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import { api } from '@/lib/api'
import type { Decision } from '@/lib/types'
import { VerdictBadge } from '@/components/ui/VerdictBadge'
import { ActionBadge } from '@/components/ui/ActionBadge'
import { ShieldCheck, FlaskConical, CheckCircle, XCircle, AlertCircle, Bot, RefreshCw } from 'lucide-react'

function StatCard({ label, value, icon: Icon, color }: { label: string; value: number; icon: React.ElementType; color: string }) {
  return (
    <div className="bg-white rounded-xl border border-border px-5 py-4 flex items-center gap-4">
      <div className={`p-2.5 rounded-lg ${color}`}>
        <Icon size={18} className="text-white" />
      </div>
      <div>
        <p className="text-2xl font-bold text-ink">{value}</p>
        <p className="text-xs text-ink-muted">{label}</p>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const [decisions, setDecisions] = useState<Decision[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(() => {
    api.listDecisions(50).then(setDecisions).finally(() => {
      setLoading(false)
      setRefreshing(false)
    })
  }, [])

  useEffect(() => { load() }, [load])

  function refresh() {
    setRefreshing(true)
    setDecisions([])
    load()
  }

  const total = decisions.length
  const passed = decisions.filter(d => d.verdict === 'pass_through').length
  const failed = decisions.filter(d => d.verdict === 'fail').length
  const needsReview = decisions.filter(d => d.verdict === 'needs_evidence' || d.verdict === 'needs_judgment').length

  const recent = decisions.slice(0, 10)

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">Dashboard</h1>
          <p className="text-sm text-ink-muted mt-0.5">Policy enforcement overview</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={refresh}
            disabled={refreshing}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-sm font-medium text-ink hover:bg-muted-bg disabled:opacity-50 transition-colors"
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} /> Refresh
          </button>
          <Link href="/policy/create" className="flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-teal text-white text-sm font-medium hover:bg-brand-teal-dark transition-colors">
            <ShieldCheck size={14} /> Create Policy
          </Link>
          <Link href="/evaluate" className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-sm font-medium text-ink hover:bg-muted-bg transition-colors">
            <FlaskConical size={14} /> Evaluate
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Total Evaluated" value={total} icon={FlaskConical} color="bg-brand-teal" />
        <StatCard label="Passed" value={passed} icon={CheckCircle} color="bg-green-500" />
        <StatCard label="Failed" value={failed} icon={XCircle} color="bg-red-500" />
        <StatCard label="Needs Review" value={needsReview} icon={AlertCircle} color="bg-yellow-500" />
      </div>

      <div className="bg-white rounded-xl border border-border overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <h2 className="text-sm font-semibold text-ink">Recent Decisions</h2>
        </div>
        {loading ? (
          <div className="px-5 py-8 text-center text-sm text-ink-muted">Loading...</div>
        ) : recent.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-ink-muted">
            No decisions yet. <Link href="/evaluate" className="text-brand-teal hover:underline">Evaluate a transaction</Link> to get started.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-muted-bg text-xs text-ink-muted uppercase tracking-wide">
              <tr>
                <th className="px-5 py-3 text-left">Transaction</th>
                <th className="px-5 py-3 text-left">Verdict</th>
                <th className="px-5 py-3 text-left">Action</th>
                <th className="px-5 py-3 text-left">Evaluated by</th>
                <th className="px-5 py-3 text-left">Time</th>
                <th className="px-5 py-3 text-left"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {recent.map(d => (
                <tr key={d.decision_id} className="hover:bg-muted-bg">
                  <td className="px-5 py-3 font-mono text-xs text-ink-muted">…{d.transaction_id.slice(-8)}</td>
                  <td className="px-5 py-3"><VerdictBadge verdict={d.verdict} /></td>
                  <td className="px-5 py-3"><ActionBadge action={d.action_taken} /></td>
                  <td className="px-5 py-3">
                    {d.agent_used ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200">
                        <Bot size={10} /> LLM judgment
                      </span>
                    ) : (
                      <span className="text-xs text-ink-muted">Rule engine</span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-xs text-ink-muted">{new Date(d.timestamp).toLocaleString()}</td>
                  <td className="px-5 py-3">
                    <Link href={`/evaluate/${d.transaction_id}`} className="text-xs text-brand-teal hover:underline">
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
