import { ReviewClient } from './ReviewClient'

export default function ReviewPolicyPage({ params }: { params: { id: string } }) {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Review Compiled Policy</h1>
        <p className="text-sm text-ink-muted mt-1">
          Review the structured rules and natural language references before approving.
        </p>
      </div>
      <ReviewClient policyId={params.id} />
    </div>
  )
}
