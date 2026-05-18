export type Verdict = 'pass_through' | 'fail' | 'needs_evidence' | 'needs_judgment' | 'abstain'
export type ActionType = 'pass_through' | 'block' | 'flag' | 'request_evidence' | 'escalate' | 'propose_clawback'
export type PolicyStatus = 'draft' | 'approved' | 'active' | 'deprecated'

export interface Transaction {
  transaction_id: string
  tenant_id: string
  employee_id: string
  amount: string
  currency: string
  merchant_name: string
  mcc_code: string
  timestamp: string
  vendor_id?: string
  card_id: string
  description?: string
}

export interface Employee {
  employee_id: string
  tenant_id: string
  name: string
  department: string
  manager_id?: string
  country: string
  role_level: string
}

export interface Vendor {
  vendor_id: string
  tenant_id: string
  name: string
  category: string
  country: string
  on_blocklist: boolean
  star_rating?: number
}

export interface ReceiptLineItem {
  name: string
  amount: string
  category?: string
}

export interface Receipt {
  receipt_id: string
  transaction_id: string
  total_amount: string
  currency: string
  line_items: ReceiptLineItem[]
  attendees?: string[]
  business_purpose?: string
}

export interface CompiledRule {
  rule_id: string
  predicate: string
  parameters: Record<string, unknown>
  applies_when?: string
  evidence_required: string[]
  action_on_violation: ActionType
  source_clause: string
}

export interface NaturalLanguageReference {
  ref_id: string
  clause_text: string
  applies_to_transaction_types: string[]
  keywords: string[]
}

export interface UnsupportedClause {
  clause_text: string
  reason: string
}

export interface CompiledPolicy {
  policy_id: string
  tenant_id: string
  version: number
  status: PolicyStatus
  structured_rules: CompiledRule[]
  natural_language_references: NaturalLanguageReference[]
  unsupported_clauses: UnsupportedClause[]
  created_at: string
  approved_by?: string
  approved_at?: string
}

export interface Decision {
  decision_id: string
  transaction_id: string
  tenant_id: string
  policy_version: number
  verdict: Verdict
  action_taken: ActionType
  rule_path: string[]
  agent_used: boolean
  agent_rationale?: string
  confidence: number
  timestamp: string
}
