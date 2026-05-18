import { PolicyInputForm } from '@/components/policy/PolicyInputForm'

export default function CreatePolicyPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Create Policy</h1>
        <p className="text-sm text-ink-muted mt-1">
          Paste your expense policy text or upload a .txt file. The model will compile it into structured rules.
        </p>
      </div>
      <div className="bg-white rounded-xl border border-border p-6">
        <PolicyInputForm />
      </div>
    </div>
  )
}
