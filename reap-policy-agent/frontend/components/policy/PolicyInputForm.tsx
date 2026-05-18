'use client'
import { useState, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { Upload, FileText, Loader2 } from 'lucide-react'

export function PolicyInputForm() {
  const [mode, setMode] = useState<'text' | 'file'>('text')
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const router = useRouter()
  const tenantId = process.env.NEXT_PUBLIC_TENANT_ID ?? 'meru-inc'

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      let policy
      if (mode === 'text') {
        if (!text.trim()) throw new Error('Policy text is required')
        policy = await api.compilePolicyText(tenantId, text)
      } else {
        if (!file) throw new Error('Please select a .txt file')
        policy = await api.uploadPolicy(tenantId, file)
      }
      router.push(`/policy/review/${policy.policy_id}`)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Compilation failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Mode toggle */}
      <div className="flex rounded-lg border border-border overflow-hidden w-fit">
        {(['text', 'file'] as const).map(m => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={`px-4 py-2 text-sm font-medium flex items-center gap-2 transition-colors ${
              mode === m ? 'bg-brand-teal text-brand-light' : 'bg-white text-ink-muted hover:bg-muted-bg'
            }`}
          >
            {m === 'text' ? <FileText size={14} /> : <Upload size={14} />}
            {m === 'text' ? 'Paste text' : 'Upload .txt'}
          </button>
        ))}
      </div>

      {mode === 'text' ? (
        <textarea
          value={text}
          onChange={e => setText(e.target.value)}
          rows={16}
          placeholder="Paste your expense policy here..."
          className="w-full rounded-lg border border-border px-4 py-3 text-sm font-mono text-ink focus:outline-none focus:ring-2 focus:ring-brand-teal resize-none"
        />
      ) : (
        <div
          onClick={() => fileRef.current?.click()}
          className="flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-border bg-white h-48 cursor-pointer hover:border-brand-teal transition-colors"
        >
          <Upload size={28} className="text-ink-muted" />
          {file ? (
            <span className="text-sm font-medium text-ink">{file.name}</span>
          ) : (
            <span className="text-sm text-ink-muted">Click to browse or drag a .txt file here</span>
          )}
          <input
            ref={fileRef}
            type="file"
            accept=".txt"
            className="hidden"
            onChange={e => setFile(e.target.files?.[0] ?? null)}
          />
        </div>
      )}

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-4 py-2">{error}</p>
      )}

      <button
        type="submit"
        disabled={loading}
        className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-brand-teal text-white text-sm font-semibold hover:bg-brand-teal-dark disabled:opacity-60 transition-colors"
      >
        {loading && <Loader2 size={14} className="animate-spin" />}
        {loading ? 'Compiling policy...' : 'Compile policy'}
      </button>
    </form>
  )
}
