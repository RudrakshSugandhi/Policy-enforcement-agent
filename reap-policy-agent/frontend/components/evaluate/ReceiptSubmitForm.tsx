'use client'
import { useState } from 'react'
import type { Decision } from '@/lib/types'
import { api } from '@/lib/api'
import { Receipt, Loader2, CheckCircle2 } from 'lucide-react'

interface Props {
  transactionId: string
  defaultCurrency?: string
  onNewDecision: (d: Decision) => void
}

export function ReceiptSubmitForm({ transactionId, defaultCurrency = 'USD', onNewDecision }: Props) {
  const [amount, setAmount] = useState('')
  const [currency, setCurrency] = useState(defaultCurrency)
  const [purpose, setPurpose] = useState('')
  const [attendees, setAttendees] = useState('')
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!amount.trim()) return
    setLoading(true)
    setError(null)
    try {
      await api.submitReceipt({
        transaction_id: transactionId,
        total_amount: amount,
        currency,
        business_purpose: purpose.trim() || undefined,
        attendees: attendees.trim()
          ? attendees.split(',').map(a => a.trim()).filter(Boolean)
          : undefined,
      })

      // Re-evaluate now that the receipt is on file
      try {
        const updated = await api.evaluate(transactionId)
        onNewDecision(updated)
      } catch {
        // Uploaded transaction not in stored data — show success without re-eval
        setSubmitted(true)
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to submit receipt')
    } finally {
      setLoading(false)
    }
  }

  if (submitted) {
    return (
      <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-4 py-3">
        <CheckCircle2 size={14} />
        Receipt saved. Re-upload the transaction file to see the updated verdict.
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <p className="text-sm text-ink-muted">
        A receipt is required for this transaction. Submit one to clear the flag and re-evaluate.
      </p>

      <div className="flex gap-3">
        <div className="flex-1">
          <label className="block text-xs text-ink-muted mb-1">Total amount <span className="text-red-500">*</span></label>
          <input
            type="number"
            step="0.01"
            min="0"
            value={amount}
            onChange={e => setAmount(e.target.value)}
            required
            placeholder="0.00"
            className="w-full rounded-lg border border-border px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-teal"
          />
        </div>
        <div className="w-28">
          <label className="block text-xs text-ink-muted mb-1">Currency</label>
          <select
            value={currency}
            onChange={e => setCurrency(e.target.value)}
            className="w-full rounded-lg border border-border px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-teal"
          >
            <option>USD</option>
            <option>EUR</option>
            <option>GBP</option>
            <option>SGD</option>
          </select>
        </div>
      </div>

      <div>
        <label className="block text-xs text-ink-muted mb-1">Business purpose</label>
        <input
          type="text"
          value={purpose}
          onChange={e => setPurpose(e.target.value)}
          placeholder="e.g. Client dinner with Acme team"
          className="w-full rounded-lg border border-border px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-teal"
        />
      </div>

      <div>
        <label className="block text-xs text-ink-muted mb-1">Attendees <span className="text-ink-muted font-normal">(optional, comma-separated)</span></label>
        <input
          type="text"
          value={attendees}
          onChange={e => setAttendees(e.target.value)}
          placeholder="Alice Smith, Bob Jones"
          className="w-full rounded-lg border border-border px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-teal"
        />
      </div>

      {error && (
        <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">{error}</p>
      )}

      <button
        type="submit"
        disabled={loading || !amount.trim()}
        className="flex items-center gap-2 px-5 py-2 rounded-lg bg-brand-teal text-white text-sm font-semibold hover:bg-brand-teal-dark disabled:opacity-60 transition-colors"
      >
        {loading ? <Loader2 size={14} className="animate-spin" /> : <Receipt size={14} />}
        {loading ? 'Submitting…' : 'Submit receipt & re-evaluate'}
      </button>
    </form>
  )
}
