from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Core entities
# ---------------------------------------------------------------------------

class Transaction(BaseModel):
    # a single card spend event submitted for policy evaluation
    transaction_id: UUID          # globally unique id for this transaction
    tenant_id: str                # company that owns this transaction
    employee_id: str              # employee who made the purchase
    amount: Decimal               # spend amount (positive, in stated currency)
    currency: str = Field(..., min_length=3, max_length=3)  # ISO 4217 e.g. USD
    merchant_name: str            # display name of the merchant
    mcc_code: str                 # merchant category code (ISO 18245)
    timestamp: datetime           # when the transaction occurred
    vendor_id: Optional[str] = None   # linked vendor record if pre-registered
    card_id: str                  # card used for the purchase
    description: Optional[str] = None  # free-text note from employee or system


class Employee(BaseModel):
    # company staff member who initiates transactions
    employee_id: str              # unique id within the tenant
    tenant_id: str                # company this employee belongs to
    name: str                     # full display name
    department: str               # e.g. Engineering, Sales
    manager_id: Optional[str] = None  # direct manager's employee_id
    country: str                  # ISO country code for per-diem rules
    role_level: str               # e.g. IC3, Manager — used for approval tiers


class Vendor(BaseModel):
    # a known merchant or supplier in the tenant's vendor master
    vendor_id: str                # unique id within the tenant
    tenant_id: str                # company this vendor record belongs to
    name: str                     # vendor display name
    category: str                 # spend category e.g. Hotels, Software
    country: str                  # vendor's operating country
    on_blocklist: bool            # true means all spend with this vendor is banned


# ---------------------------------------------------------------------------
# Receipt
# ---------------------------------------------------------------------------

class ReceiptLineItem(BaseModel):
    # a single line on a receipt (one item or service)
    name: str                     # description of the item
    amount: Decimal               # cost of this line item
    category: Optional[str] = None  # optional spend category for this line


class Receipt(BaseModel):
    # OCR'd or parsed receipt attached to a transaction
    receipt_id: UUID              # unique id for this receipt
    transaction_id: UUID          # transaction this receipt is evidence for
    total_amount: Decimal         # sum of all line items
    currency: str = Field(..., min_length=3, max_length=3)  # ISO 4217
    line_items: list[ReceiptLineItem]  # itemised breakdown of the spend
    attendees: Optional[list[str]] = None       # names present (meals, events)
    business_purpose: Optional[str] = None      # employee-stated reason for spend


# ---------------------------------------------------------------------------
# Policy enums
# ---------------------------------------------------------------------------

class PredicateType(str, Enum):
    # the kind of check a structured rule performs
    amount_cap = "amount_cap"                     # spend exceeds a fixed limit
    amount_requires_receipt = "amount_requires_receipt"  # spend above threshold needs receipt
    vendor_blocklist = "vendor_blocklist"         # vendor is explicitly banned
    vendor_allowlist = "vendor_allowlist"         # vendor not on approved list
    mcc_ban = "mcc_ban"                           # merchant category is banned
    hotel_star_max = "hotel_star_max"             # hotel star rating exceeds limit
    per_diem_cap = "per_diem_cap"                 # daily spend exceeds country rate
    category_pre_approval = "category_pre_approval"  # category needs prior approval
    requires_attendee_note = "requires_attendee_note"  # meal/event needs attendee list


class ActionType(str, Enum):
    # what the agent does when a rule fires or a decision is made
    pass_through = "pass_through"       # compliant, no action needed
    block = "block"                     # hard stop — transaction should not proceed
    flag = "flag"                       # mark for finance review, do not block
    request_evidence = "request_evidence"  # ask employee for receipt or justification
    escalate = "escalate"               # route to manager or finance for approval
    propose_clawback = "propose_clawback"  # recommend recovering funds (needs human sign-off)


class PolicyStatus(str, Enum):
    # lifecycle state of a compiled policy version
    draft = "draft"           # compiled but not yet reviewed
    approved = "approved"     # reviewed and signed off, not yet live
    active = "active"         # currently used to evaluate transactions
    deprecated = "deprecated" # replaced by a newer version


# ---------------------------------------------------------------------------
# Compiled policy models
# ---------------------------------------------------------------------------

class CompiledRule(BaseModel):
    # a single machine-executable rule extracted from natural language policy
    rule_id: str                          # unique id within the policy version
    predicate: PredicateType              # the type of check this rule performs
    parameters: dict                      # threshold values or lists for the check
    applies_when: Optional[str] = None    # optional condition (e.g. role_level == IC)
    evidence_required: list[str] = Field(default_factory=list)  # docs needed to clear the rule
    action_on_violation: ActionType       # what happens if this rule fails
    source_clause: str                    # original natural language this was compiled from


class NaturalLanguageReference(BaseModel):
    # policy clause kept as text for LLM judgment on ambiguous cases
    ref_id: str                                   # unique id within the policy version
    clause_text: str                              # verbatim policy wording
    applies_to_transaction_types: list[str]       # transaction types this clause covers
    keywords: list[str]                           # terms used to match transactions to this clause


class UnsupportedClause(BaseModel):
    # policy clause the compiler could not turn into a structured rule
    clause_text: str   # verbatim wording from the uploaded policy
    reason: str        # why compilation failed (e.g. too vague, missing parameters)


class CompiledPolicy(BaseModel):
    # a fully compiled and versioned policy ready to evaluate transactions
    policy_id: UUID                                        # unique id for this policy
    tenant_id: str                                         # company this policy belongs to
    version: int                                           # monotonically increasing version number
    status: PolicyStatus                                   # current lifecycle state
    structured_rules: list[CompiledRule]                   # deterministic rules to run first
    natural_language_references: list[NaturalLanguageReference]  # clauses sent to LLM if needed
    unsupported_clauses: list[UnsupportedClause]           # clauses that could not be compiled
    created_at: datetime                                   # when this version was compiled
    approved_by: Optional[str] = None                      # employee_id of the approver
    approved_at: Optional[datetime] = None                 # when approval was given


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

class Verdict(str, Enum):
    # the overall outcome of evaluating one transaction
    pass_through = "pass_through"     # transaction is compliant
    fail = "fail"                     # transaction violates policy
    needs_evidence = "needs_evidence" # cannot decide until receipt/docs are provided
    needs_judgment = "needs_judgment" # ambiguous — routed to LLM or human
    abstain = "abstain"               # no applicable rule found, no decision made


class Decision(BaseModel):
    # the final output of the agent for one transaction
    decision_id: UUID                     # unique id for this decision
    transaction_id: UUID                  # transaction that was evaluated
    tenant_id: str                        # company context
    policy_version: int                   # policy version used at evaluation time
    verdict: Verdict                      # overall outcome
    action_taken: ActionType              # action the agent dispatched
    rule_path: list[str] = Field(default_factory=list)  # ordered list of rule_ids that fired
    agent_used: bool                      # true if LLM judgment was invoked
    agent_rationale: Optional[str] = None  # LLM explanation when agent_used is true
    confidence: float = Field(..., ge=0.0, le=1.0)  # 0 = uncertain, 1 = fully deterministic
    timestamp: datetime                   # when the decision was made


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

class AuditEntry(BaseModel):
    # immutable record of one step in the evaluation pipeline
    entry_id: UUID          # unique id for this audit entry
    transaction_id: UUID    # transaction being evaluated
    step: str               # pipeline step name e.g. rule_engine, judgment_agent
    inputs: dict            # snapshot of inputs passed into this step
    outputs: dict           # snapshot of outputs produced by this step
    timestamp: datetime     # when this step executed
