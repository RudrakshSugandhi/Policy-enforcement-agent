"""
Policy compiler agent.

Takes raw natural language policy text and produces a CompiledPolicy (status: draft)
with three layers of output:
  - structured_rules     — measurable checks mapped to a PredicateType
  - natural_language_references — fuzzy clauses forwarded to the LLM at eval time
  - unsupported_clauses  — clauses that cannot be enforced by this system

Uses Outlines + Ollama (Qwen 2.5 7B) to constrain LLM output to the schema.
Retries once with the validation error in the prompt if the first attempt fails.
"""

import asyncio
import json
import os
from dataclasses import dataclass, field as _field
from datetime import datetime, timezone
from uuid import UUID

import ollama as ollama_lib
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from app.schemas import (
    CompiledPolicy,
    CompiledRule,
    NaturalLanguageReference,
    PolicyStatus,
    UnsupportedClause,
)

load_dotenv()

_OLLAMA_HOST = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")


# ---------------------------------------------------------------------------
# LLM output schema — only the fields the model generates.
# UUIDs, timestamps, tenant context are filled in by Python after compilation.
# ---------------------------------------------------------------------------

class _CompilationResult(BaseModel):
    structured_rules: list[CompiledRule]
    natural_language_references: list[NaturalLanguageReference]
    unsupported_clauses: list[UnsupportedClause]


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_PREDICATE_SCHEMAS = """
amount_cap              → {"cap": <number>, "currency": "<USD|EUR|GBP|SGD>"}
amount_requires_receipt → {"threshold": <number>, "currency": "<USD|EUR|GBP|SGD>"}
vendor_blocklist        → {"vendors": ["<name>", ...]}
vendor_allowlist        → {"vendors": ["<name>", ...]}
mcc_ban                 → {"mcc_codes": ["<4-digit code>", ...]}
hotel_star_max          → {"max_stars": <number>}
per_diem_cap            → {"cap": <number>, "currency": "<code>", "country": "<ISO or null>"}
category_pre_approval   → {"categories": ["<name>", ...], "approval_from": "<role>"}
requires_attendee_note  → {"transaction_types": ["meal"|"entertainment"|"team_event"]}
  NOTE: requires_attendee_note means the employee must LIST attendees as evidence.
        Do NOT use it when a clause makes reimbursability CONTINGENT on who is present
        (e.g. "only when clients are present"). That kind of conditional requires human
        verification and must go in natural_language_references.
"""

_ACTION_OPTIONS = (
    "pass_through | block | flag | request_evidence | escalate | propose_clawback"
)

_SYSTEM_PROMPT = f"""You are a policy compiler for a financial spend management system.
Your job is to read a company expense policy and compile each clause into one of three layers.

PREDICATE TYPES and their required parameter shapes:
{_PREDICATE_SCHEMAS}

ACTION TYPES (choose the most appropriate for each violation):
{_ACTION_OPTIONS}

CLASSIFICATION RULES:
1. Use "structured" when the clause is a measurable comparison: amount vs threshold, vendor in a list,
   category match, hotel star rating, MCC code, per-diem cap. Return a CompiledRule.
2. Use "natural_language" when the clause requires human judgment: "reasonable", "good judgment",
   "business necessity", "client present". Return a NaturalLanguageReference with relevant keywords.
3. Use "unsupported" when the clause cannot be enforced by a transaction-level agent: reporting
   deadlines, HR procedures, governance obligations. Return an UnsupportedClause with a one-line reason.

IMPORTANT RULES:
- Process every sentence independently. A single numbered clause may produce multiple entries
  across different layers. Never collapse two sentences into one entry; never silently drop a sentence.
- Return exactly one top-level JSON object with these keys:
  "structured_rules", "natural_language_references", "unsupported_clauses".
  Each key must be present and must contain an array.
- Prefer "structured" over "natural_language" wherever a measurable threshold or list exists.
- Any clause that explicitly names banned or blocked vendors MUST use predicate "vendor_blocklist". This is always structured, never natural_language.
- Any SaaS, software, travel, or category purchase requiring pre-approval MUST use predicate
  "category_pre_approval". Include the category and approver role in parameters.
- CONDITIONAL HUMAN-JUDGMENT: If a sentence makes reimbursability contingent on a condition
  that requires human observation to verify (e.g. "only when clients are present", "only if
  business necessity is demonstrated", "provided the occasion warrants it"), classify the whole
  sentence as natural_language — even if it also contains a numeric threshold. The unverifiable
  condition is what matters for classification. Do NOT use requires_attendee_note as a substitute
  for this — requires_attendee_note is only for evidence collection (listing attendee names).
- NEVER DUPLICATE: If a clause is already in natural_language_references, do NOT also add it as
  a structured rule. Each clause must appear in exactly one layer.
- PERCENTAGE LIMITS: Do not use amount_cap for percentage-based limits (e.g. "not exceed 20% of
  the bill"). Percentage limits require runtime calculation against another value and must go in
  natural_language_references.
- A clause about quarterly reports to the board, HR review, reporting deadlines, or governance obligations
  is unsupported at transaction level. Put it in unsupported_clauses.
- Always copy the original clause text verbatim into source_clause (for CompiledRule) or
  clause_text (for NaturalLanguageReference / UnsupportedClause).
- For rule_id use "rule-001", "rule-002", etc. For ref_id use "ref-001", "ref-002", etc.
- For evidence_required: include "receipt" when a receipt is needed, "manager_approval" when
  manager sign-off is needed, else leave empty.
- For hotel per-location caps, produce one rule per location.
- Output valid JSON only. Do not include any explanation outside the JSON.

EXAMPLE CompiledRule:
{{
  "rule_id": "rule-001",
  "predicate": "amount_requires_receipt",
  "parameters": {{"threshold": 75, "currency": "USD"}},
  "applies_when": null,
  "evidence_required": ["receipt"],
  "action_on_violation": "request_evidence",
  "source_clause": "Receipts are required for any expense over 75 USD."
}}

EXAMPLE NaturalLanguageReference:
{{
  "ref_id": "ref-001",
  "clause_text": "Employees should use good judgment for meal expenses.",
  "applies_to_transaction_types": ["meal", "entertainment"],
  "keywords": ["good judgment", "reasonable", "meal"]
}}

EXAMPLE CompiledRule (vendor blocklist):
{{
  "rule_id": "rule-002",
  "predicate": "vendor_blocklist",
  "parameters": {{"vendors": ["Competitor Corp", "RivalCo"]}},
  "applies_when": null,
  "evidence_required": [],
  "action_on_violation": "block",
  "source_clause": "Banned vendors include Competitor Corp and RivalCo."
}}

EXAMPLE UnsupportedClause:
{{
  "clause_text": "Quarterly expense reports must be submitted to the board.",
  "reason": "Reporting deadline — not enforceable at transaction level."
}}

SINGLE-CLAUSE EXAMPLE INPUT:
Banned vendors include Competitor Corp and RivalCo.

SINGLE-CLAUSE EXAMPLE OUTPUT:
{{
  "structured_rules": [
    {{
      "rule_id": "rule-001",
      "predicate": "vendor_blocklist",
      "parameters": {{"vendors": ["Competitor Corp", "RivalCo"]}},
      "applies_when": null,
      "evidence_required": [],
      "action_on_violation": "block",
      "source_clause": "Banned vendors include Competitor Corp and RivalCo."
    }}
  ],
  "natural_language_references": [],
  "unsupported_clauses": []
}}

SINGLE-CLAUSE EXAMPLE INPUT:
SaaS subscriptions above 500 USD per month require pre-approval from the department head.

SINGLE-CLAUSE EXAMPLE OUTPUT:
{{
  "structured_rules": [
    {{
      "rule_id": "rule-001",
      "predicate": "category_pre_approval",
      "parameters": {{"categories": ["SaaS subscriptions"], "approval_from": "department head"}},
      "applies_when": "amount > 500 USD per month",
      "evidence_required": ["manager_approval"],
      "action_on_violation": "escalate",
      "source_clause": "SaaS subscriptions above 500 USD per month require pre-approval from the department head."
    }}
  ],
  "natural_language_references": [],
  "unsupported_clauses": []
}}

COMPLETE EXAMPLE INPUT:
1. Receipts are required for any expense over 75 USD.
2. SaaS subscriptions above 500 USD per month require pre-approval from the department head.
3. Banned vendors: Competitor Corp and RivalCo.
4. Meal expenses are capped at 80 USD per person. Alcohol is reimbursable only when clients are present and must not exceed 20% of the total bill.
5. Quarterly expense reports must be submitted to the board.

COMPLETE EXAMPLE OUTPUT:
{{
  "structured_rules": [
    {{
      "rule_id": "rule-001",
      "predicate": "amount_requires_receipt",
      "parameters": {{"threshold": 75, "currency": "USD"}},
      "applies_when": null,
      "evidence_required": ["receipt"],
      "action_on_violation": "request_evidence",
      "source_clause": "Receipts are required for any expense over 75 USD."
    }},
    {{
      "rule_id": "rule-002",
      "predicate": "category_pre_approval",
      "parameters": {{"categories": ["SaaS subscriptions"], "approval_from": "department head"}},
      "applies_when": "amount > 500 USD per month",
      "evidence_required": ["manager_approval"],
      "action_on_violation": "escalate",
      "source_clause": "SaaS subscriptions above 500 USD per month require pre-approval from the department head."
    }},
    {{
      "rule_id": "rule-003",
      "predicate": "vendor_blocklist",
      "parameters": {{"vendors": ["Competitor Corp", "RivalCo"]}},
      "applies_when": null,
      "evidence_required": [],
      "action_on_violation": "block",
      "source_clause": "Banned vendors: Competitor Corp and RivalCo."
    }},
    {{
      "rule_id": "rule-004",
      "predicate": "amount_cap",
      "parameters": {{"cap": 80, "currency": "USD"}},
      "applies_when": null,
      "evidence_required": [],
      "action_on_violation": "flag",
      "source_clause": "Meal expenses are capped at 80 USD per person."
    }}
  ],
  "natural_language_references": [
    {{
      "ref_id": "ref-001",
      "clause_text": "Alcohol is reimbursable only when clients are present and must not exceed 20% of the total bill.",
      "applies_to_transaction_types": ["meal", "entertainment"],
      "keywords": ["alcohol", "clients present", "client dinner", "20%"]
    }}
  ],
  "unsupported_clauses": [
    {{
      "clause_text": "Quarterly expense reports must be submitted to the board.",
      "reason": "Board reporting is a governance obligation, not a transaction-level rule."
    }}
  ]
}}
"""


# ---------------------------------------------------------------------------
# Compiler
# ---------------------------------------------------------------------------

_OLLAMA_SCHEMA = _CompilationResult.model_json_schema()


def _run_generation(prompt: str) -> _CompilationResult:
    """Synchronous Ollama call with temperature=0 for deterministic output."""
    client = ollama_lib.Client(host=_OLLAMA_HOST)
    response = client.generate(
        model=_MODEL,
        prompt=prompt,
        format=_OLLAMA_SCHEMA,
        options={"temperature": 0},
    )
    raw = response.response
    data = json.loads(raw) if isinstance(raw, str) else raw
    return _CompilationResult.model_validate(data)


async def compile_policy(
    tenant_id: str,
    policy_id: str,
    policy_text: str,
    version: int = 1,
) -> CompiledPolicy:
    """
    Compile a natural language policy into a CompiledPolicy with status=draft.

    Retries once if the LLM output fails Pydantic validation.
    Raises RuntimeError if both attempts fail (agent abstaining).
    """
    user_prompt = f"{_SYSTEM_PROMPT}\n\nPolicy text to compile:\n{policy_text}"

    # attempt 1
    try:
        result = await asyncio.to_thread(_run_generation, user_prompt)
    except (ValidationError, Exception) as first_error:
        # attempt 2 — inject the validation error so the model can self-correct
        retry_prompt = (
            f"{user_prompt}\n\n"
            f"Your previous response failed validation with this error:\n{first_error}\n"
            "Please fix the JSON and return a valid response."
        )
        try:
            result = await asyncio.to_thread(_run_generation, retry_prompt)
        except Exception as second_error:
            raise RuntimeError(
                f"Policy compiler failed after two attempts. "
                f"First error: {first_error}. Second error: {second_error}"
            ) from second_error

    return CompiledPolicy(
        policy_id=UUID(policy_id),   # reuse the ID assigned at upload time
        tenant_id=tenant_id,
        version=version,
        status=PolicyStatus.draft,
        structured_rules=result.structured_rules,
        natural_language_references=result.natural_language_references,
        unsupported_clauses=result.unsupported_clauses,
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Policy diff
# ---------------------------------------------------------------------------

@dataclass
class PolicyDiff:
    added_rules:       list[CompiledRule]                                       = _field(default_factory=list)
    removed_rules:     list[CompiledRule]                                       = _field(default_factory=list)
    changed_rules:     list[tuple[CompiledRule, CompiledRule]]                  = _field(default_factory=list)
    added_refs:        list[NaturalLanguageReference]                           = _field(default_factory=list)
    removed_refs:      list[NaturalLanguageReference]                           = _field(default_factory=list)
    changed_refs:      list[tuple[NaturalLanguageReference, NaturalLanguageReference]] = _field(default_factory=list)
    added_unsupported: list[UnsupportedClause]                                  = _field(default_factory=list)
    removed_unsupported: list[UnsupportedClause]                                = _field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.added_rules or self.removed_rules or self.changed_rules
            or self.added_refs or self.removed_refs or self.changed_refs
            or self.added_unsupported or self.removed_unsupported
        )

    @property
    def total(self) -> int:
        return (
            len(self.added_rules) + len(self.removed_rules) + len(self.changed_rules)
            + len(self.added_refs) + len(self.removed_refs) + len(self.changed_refs)
            + len(self.added_unsupported) + len(self.removed_unsupported)
        )


def diff_policies(old: CompiledPolicy, new: CompiledPolicy) -> PolicyDiff:
    """Compare two compiled policies and return a structured diff.

    Match strategy: rules are keyed by (source_clause, predicate) — the verbatim
    policy wording plus the predicate type. This is stable across re-compilations of
    an unchanged clause and correctly surfaces edited text as a remove + add pair.
    NL references and unsupported clauses are keyed by clause_text alone.
    """
    diff = PolicyDiff()

    # --- Structured rules ---
    def _rule_key(r: CompiledRule) -> str:
        return f"{r.source_clause.strip()}|{r.predicate.value}"

    def _rule_content(r: CompiledRule) -> str:
        return json.dumps(
            {"parameters": r.parameters, "action": r.action_on_violation.value,
             "evidence": sorted(r.evidence_required)},
            sort_keys=True,
        )

    old_rules = {_rule_key(r): r for r in old.structured_rules}
    new_rules = {_rule_key(r): r for r in new.structured_rules}

    for key in sorted(set(old_rules) | set(new_rules)):
        o, n = old_rules.get(key), new_rules.get(key)
        if o is None:
            diff.added_rules.append(n)
        elif n is None:
            diff.removed_rules.append(o)
        elif _rule_content(o) != _rule_content(n):
            diff.changed_rules.append((o, n))

    # --- Natural language references ---
    def _ref_content(r: NaturalLanguageReference) -> str:
        return json.dumps(
            {"keywords": sorted(r.keywords),
             "types": sorted(r.applies_to_transaction_types)},
        )

    old_refs = {r.clause_text.strip(): r for r in old.natural_language_references}
    new_refs = {r.clause_text.strip(): r for r in new.natural_language_references}

    for key in sorted(set(old_refs) | set(new_refs)):
        o, n = old_refs.get(key), new_refs.get(key)
        if o is None:
            diff.added_refs.append(n)
        elif n is None:
            diff.removed_refs.append(o)
        elif _ref_content(o) != _ref_content(n):
            diff.changed_refs.append((o, n))

    # --- Unsupported clauses ---
    old_unsup = {u.clause_text.strip(): u for u in old.unsupported_clauses}
    new_unsup = {u.clause_text.strip(): u for u in new.unsupported_clauses}

    for key in sorted(set(old_unsup) | set(new_unsup)):
        if key not in old_unsup:
            diff.added_unsupported.append(new_unsup[key])
        elif key not in new_unsup:
            diff.removed_unsupported.append(old_unsup[key])

    return diff


_DIFF_SEP = "─" * 62


def print_diff(diff: PolicyDiff, old_version: int, new_version: int) -> None:
    """Print a human-readable policy diff to stdout."""
    print(f"\n{_DIFF_SEP}")
    print(f"  DIFF  v{old_version} → v{new_version}")
    print(_DIFF_SEP)

    if not diff.has_changes:
        print("\n  No changes in compiled output.\n")
        return

    if diff.added_rules or diff.removed_rules or diff.changed_rules:
        print("\n  Structured rules:")
        for r in diff.added_rules:
            print(f"    + ADDED    {r.predicate.value}  {json.dumps(r.parameters)}")
            print(f"               \"{r.source_clause[:70]}\"")
        for r in diff.removed_rules:
            print(f"    - REMOVED  {r.predicate.value}  {json.dumps(r.parameters)}")
            print(f"               \"{r.source_clause[:70]}\"")
        for old_r, new_r in diff.changed_rules:
            print(f"    ~ CHANGED  {old_r.predicate.value}")
            print(f"               was: {json.dumps(old_r.parameters)}  action={old_r.action_on_violation.value}")
            print(f"               now: {json.dumps(new_r.parameters)}  action={new_r.action_on_violation.value}")

    if diff.added_refs or diff.removed_refs or diff.changed_refs:
        print("\n  Natural language references:")
        for r in diff.added_refs:
            print(f"    + ADDED    \"{r.clause_text[:70]}\"")
        for r in diff.removed_refs:
            print(f"    - REMOVED  \"{r.clause_text[:70]}\"")
        for old_r, new_r in diff.changed_refs:
            print(f"    ~ CHANGED  \"{old_r.clause_text[:55]}\"")
            print(f"               was keywords: {old_r.keywords}")
            print(f"               now keywords: {new_r.keywords}")

    if diff.added_unsupported or diff.removed_unsupported:
        print("\n  Unsupported clauses:")
        for u in diff.added_unsupported:
            print(f"    + ADDED    \"{u.clause_text[:70]}\"")
        for u in diff.removed_unsupported:
            print(f"    - REMOVED  \"{u.clause_text[:70]}\"")

    print(f"\n  {diff.total} change(s) total.\n")
