import type { CompiledPolicy, Decision, Employee, Receipt, Transaction, Vendor } from './types'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail.detail ?? res.statusText)
  }
  return res.json()
}

export const api = {
  // Policy
  compilePolicyText: (tenantId: string, policyText: string) =>
    request<CompiledPolicy>('/policies/compile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tenant_id: tenantId, policy_text: policyText }),
    }),

  uploadPolicy: (tenantId: string, file: File) => {
    const form = new FormData()
    form.append('tenant_id', tenantId)
    form.append('file', file)
    return request<CompiledPolicy>('/policies/upload', { method: 'POST', body: form })
  },

  getPolicy: (policyId: string) =>
    request<CompiledPolicy>(`/policies/${policyId}`),

  approvePolicy: (policyId: string, reviewerId = 'reviewer') =>
    request<CompiledPolicy>(`/policies/${policyId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reviewer_id: reviewerId }),
    }),

  getActivePolicy: (tenantId: string) =>
    request<CompiledPolicy>(`/policy/active?tenant_id=${encodeURIComponent(tenantId)}`),

  // Evaluation
  evaluate: (transactionId: string) =>
    request<Decision>('/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transaction_id: transactionId }),
    }),

  evaluateUpload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Decision>('/evaluate/upload', { method: 'POST', body: form })
  },

  // Receipts
  submitReceipt: (data: {
    transaction_id: string
    total_amount: string
    currency: string
    business_purpose?: string
    attendees?: string[]
  }) =>
    request<Receipt>('/receipts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  // Data
  listTransactions: () => request<Transaction[]>('/transactions'),
  listEmployees: () => request<Employee[]>('/employees'),
  listVendors: () => request<Vendor[]>('/vendors'),
  listReceipts: () => request<Receipt[]>('/receipts'),
  listDecisions: (limit = 50) => request<Decision[]>(`/decisions?limit=${limit}`),
  getDecisions: (transactionId: string) => request<Decision[]>(`/decisions/${transactionId}`),
}
