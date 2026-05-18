'use client'
import { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import type { Transaction, Employee, Vendor, Receipt, Decision } from '@/lib/types'
import { TransactionPreviewCard } from './TransactionPreviewCard'
import { DecisionPanel } from './DecisionPanel'
import { Loader2 } from 'lucide-react'

export function StoredTransactionTab() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [employees, setEmployees] = useState<Employee[]>([])
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [receipts, setReceipts] = useState<Receipt[]>([])
  const [selected, setSelected] = useState<Transaction | null>(null)
  const [decision, setDecision] = useState<Decision | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dataLoading, setDataLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.listTransactions(), api.listEmployees(), api.listVendors(), api.listReceipts()])
      .then(([t, e, v, r]) => { setTransactions(t); setEmployees(e); setVendors(v); setReceipts(r) })
      .finally(() => setDataLoading(false))
  }, [])

  const empMap = Object.fromEntries(employees.map(e => [e.employee_id, e]))
  const vendorMap = Object.fromEntries(vendors.map(v => [v.vendor_id, v]))
  const receiptMap = Object.fromEntries(receipts.map(r => [r.transaction_id, r]))

  function getVendor(txn: Transaction) {
    if (txn.vendor_id) return vendorMap[txn.vendor_id]
    return vendors.find(v => v.name.toLowerCase() === txn.merchant_name.toLowerCase())
  }

  async function evaluate() {
    if (!selected) return
    setLoading(true)
    setError(null)
    setDecision(null)
    try {
      const d = await api.evaluate(selected.transaction_id)
      setDecision(d)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Evaluation failed')
    } finally {
      setLoading(false)
    }
  }

  if (dataLoading) return (
    <div className="flex items-center justify-center py-16 text-ink-muted gap-2">
      <Loader2 size={16} className="animate-spin" /> Loading transactions...
    </div>
  )

  return (
    <div className="space-y-5">
      <div>
        <label className="block text-sm font-medium text-ink mb-2">Select transaction</label>
        <select
          className="w-full rounded-lg border border-border px-3 py-2.5 text-sm text-ink bg-white focus:outline-none focus:ring-2 focus:ring-brand-teal"
          value={selected?.transaction_id ?? ''}
          onChange={e => {
            const txn = transactions.find(t => t.transaction_id === e.target.value) ?? null
            setSelected(txn)
            setDecision(null)
            setError(null)
          }}
        >
          <option value="">— choose a transaction —</option>
          {transactions.map(txn => {
            const emp = empMap[txn.employee_id]
            return (
              <option key={txn.transaction_id} value={txn.transaction_id}>
                {txn.merchant_name} — {txn.amount} {txn.currency}
                {emp ? ` — ${emp.name} (${emp.department})` : ''}
              </option>
            )
          })}
        </select>
      </div>

      {selected && (
        <TransactionPreviewCard
          transaction={selected}
          employee={empMap[selected.employee_id]}
          vendor={getVendor(selected)}
          receipt={receiptMap[selected.transaction_id]}
        />
      )}

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-4 py-2">{error}</p>
      )}

      <button
        onClick={evaluate}
        disabled={!selected || loading}
        className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-brand-teal text-white text-sm font-semibold hover:bg-brand-teal-dark disabled:opacity-50 transition-colors"
      >
        {loading && <Loader2 size={14} className="animate-spin" />}
        {loading ? 'Evaluating...' : 'Evaluate'}
      </button>

      {decision && (
        <div>
          <h3 className="text-sm font-semibold text-ink mb-3">Decision</h3>
          <DecisionPanel decision={decision} />
          <button
            onClick={() => { setSelected(null); setDecision(null) }}
            className="mt-3 text-sm text-brand-teal hover:underline"
          >
            Evaluate another
          </button>
        </div>
      )}
    </div>
  )
}
