'use client'
import { useState, useRef } from 'react'
import { api } from '@/lib/api'
import type { Transaction, Decision } from '@/lib/types'
import { TransactionPreviewCard } from './TransactionPreviewCard'
import { DecisionPanel } from './DecisionPanel'
import { Upload, Loader2, Download } from 'lucide-react'

export function UploadTransactionTab() {
  const [file, setFile] = useState<File | null>(null)
  const [parsed, setParsed] = useState<Transaction | null>(null)
  const [parseError, setParseError] = useState<string | null>(null)
  const [decision, setDecision] = useState<Decision | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  function handleFile(f: File) {
    setFile(f)
    setParseError(null)
    setDecision(null)
    const reader = new FileReader()
    reader.onload = e => {
      try {
        const data = JSON.parse(e.target?.result as string)
        setParsed(data as Transaction)
      } catch {
        setParseError('Invalid JSON file')
        setParsed(null)
      }
    }
    reader.readAsText(f)
  }

  async function evaluate() {
    if (!file) return
    setLoading(true)
    setError(null)
    setDecision(null)
    try {
      const d = await api.evaluateUpload(file)
      setDecision(d)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Evaluation failed')
    } finally {
      setLoading(false)
    }
  }

  function reset() {
    setFile(null)
    setParsed(null)
    setDecision(null)
    setError(null)
  }

  return (
    <div className="space-y-5">
      <div
        onClick={() => fileRef.current?.click()}
        onDragOver={e => e.preventDefault()}
        onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handleFile(f) }}
        className="flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-border bg-white h-40 cursor-pointer hover:border-brand-teal transition-colors"
      >
        <Upload size={24} className="text-ink-muted" />
        {file ? (
          <span className="text-sm font-medium text-ink">{file.name}</span>
        ) : (
          <span className="text-sm text-ink-muted">Drag & drop or click to upload a .json transaction file</span>
        )}
        <input ref={fileRef} type="file" accept=".json" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }} />
      </div>

      <a
        href="/sample-transaction.json"
        download="sample-transaction.json"
        className="inline-flex items-center gap-1.5 text-xs text-brand-teal hover:underline"
      >
        <Download size={12} /> Download sample transaction JSON
      </a>

      {parseError && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-4 py-2">{parseError}</p>
      )}

      {parsed && !parseError && (
        <TransactionPreviewCard transaction={parsed} />
      )}

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-4 py-2">{error}</p>
      )}

      <button
        onClick={evaluate}
        disabled={!file || !!parseError || loading}
        className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-brand-teal text-white text-sm font-semibold hover:bg-brand-teal-dark disabled:opacity-50 transition-colors"
      >
        {loading && <Loader2 size={14} className="animate-spin" />}
        {loading ? 'Evaluating...' : 'Evaluate'}
      </button>

      {decision && (
        <div>
          <h3 className="text-sm font-semibold text-ink mb-3">Decision</h3>
          <DecisionPanel decision={decision} />
          <button onClick={reset} className="mt-3 text-sm text-brand-teal hover:underline">
            Evaluate another
          </button>
        </div>
      )}
    </div>
  )
}
