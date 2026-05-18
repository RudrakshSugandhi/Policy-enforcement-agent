'use client'
import { useState } from 'react'
import { StoredTransactionTab } from '@/components/evaluate/StoredTransactionTab'
import { UploadTransactionTab } from '@/components/evaluate/UploadTransactionTab'

const tabs = [
  { id: 'stored', label: 'Stored Transactions' },
  { id: 'upload', label: 'Upload JSON' },
] as const

export default function EvaluatePage() {
  const [active, setActive] = useState<'stored' | 'upload'>('stored')

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Evaluate Transaction</h1>
        <p className="text-sm text-ink-muted mt-1">
          Select a stored transaction or upload a custom JSON file to evaluate against the active policy.
        </p>
      </div>

      <div className="bg-white rounded-xl border border-border overflow-hidden">
        <div className="flex border-b border-border">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setActive(t.id)}
              className={`px-5 py-3 text-sm font-medium transition-colors ${
                active === t.id
                  ? 'text-brand-teal border-b-2 border-brand-teal -mb-px'
                  : 'text-ink-muted hover:text-ink'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="p-6">
          {active === 'stored' ? <StoredTransactionTab /> : <UploadTransactionTab />}
        </div>
      </div>
    </div>
  )
}
