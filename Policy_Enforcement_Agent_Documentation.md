# Policy Enforcement Agent — Design Doc

## Three Important Evaluation Areas

1. **Product thinking**: what problem we solve, for whom, and what actions the agent should take.
2. **Architecture and technology choices**: how policies, rules, LLMs, receipts, and actions work together.
3. **Production-ready solution**: how the system handles safety, auditability, versioning, scale, and human review.

---

## Product Context

**Workflow chosen: Policy Enforcement Agent** — Workflow 2 from the brief.

**Why this workflow:**

- **Biggest financial impact.** Roughly 5% of customer spend goes out of policy and most of it is never recovered. A policy enforcement agent addresses this directly — saving real money every month, not just reducing close-time overhead.
- **Cuts across all of Reap.** Card spend, bill pay, and Optimize all involve money that must follow rules. A policy agent is the right foundation for the AI CFO vision — it is not a narrow feature but a core primitive.
- **Strongest production-readiness signal.** Policy enforcement forces genuine engagement with autonomy, reversibility, and human oversight in a way the other workflows do not. Getting this right demonstrates the hardest parts of building trustworthy agents.

**The core loop:** ingest policies written in natural language → evaluate each transaction against them → take the right action → close the loop with the employee.

---

## 1. Goal

- Build an agent that evaluates employee spend against company policy.
- Policies include per-diem caps, receipt rules, vendor bans, hotel limits, category bans, approvals, and clawback rules.
- The agent should reduce manual finance review by deciding what action to take for each transaction.

---

## 2. Product Thinking

- **Main user**: finance operations team.
- **Secondary user**: employee who needs clear next steps.
- **Main value**: catch out-of-policy spend faster and reduce manual chasing.
- Employee experience matters: messages must be specific, fair, and easy to act on.
- High-stakes actions like clawback should require human approval.
- The product should start with reversible actions: flag, request receipt, ask clarification, and escalate.

---

## 3. Key Assumptions for 4–6 Hour Build

- Build the core agent first, not a full finance platform.
- Frontend can be minimal; API/demo output is enough if time is tight.
- Policy input starts as text. PDF/Word OCR can be future work.
- Receipts can be represented as parsed sample data in the first version.
- Real blocking, clawback, and payroll deduction are not executed in the demo.
- The agent returns proposed actions and employee-facing messages.
- Reap already provides transaction events, OCR'd receipts, vendor records, employees, and per-tenant chart of accounts. We mock these but the data model is multi-tenant throughout.
- Policies are uploaded as natural language by the customer and change a few times per year.

---

## 4. High-Level Workflow

1. Company uploads policy.
2. Agent compiles policy into hybrid representation.
3. Finance admin approves compiled policy.
4. Transaction arrives.
5. Agent loads employee, merchant, receipt, and policy context.
6. Structured rules run first.
7. LLM runs only if the case is ambiguous.
8. Agent returns decision and action.
9. Employee receives message.
10. Audit log records everything.

---

## 5. Architecture and Technology Choices

- **Backend**: FastAPI for simple API endpoints and quick iteration.
- **Agent layer**: policy compiler, rule engine, LLM judgment tool, action dispatcher.
- **Storage**: simple database tables for policies, policy versions, transactions, decisions, and audit logs.
- **Frontend**: optional React/Next.js UI for upload, transaction test, and decision review.
- **LLM**: [Qwen 2.5 7B](https://ollama.com/library/qwen2.5) served locally via **Ollama**. Chosen for its strong instruction-following on structured tasks, low memory footprint (runs on a MacBook), and zero API cost. Accessed through an OpenAI-compatible client so the model can be swapped with a single config change.
- **OCR**: future extension for PDF/Word policies and receipt images.

---

## 6. Defended Choice: Hybrid Policy Representation

We should not use LLM-only enforcement. We should not use rules-only enforcement. The best choice is **hybrid: structured rules plus natural-language reference**.

### Structured Rules
- Used for measurable checks.
- Examples: `amount > cap`, vendor in banned list, receipt missing, category banned, hotel star rating too high.
- Benefits: fast, cheap, reliable, auditable, and testable.

### Natural-Language Reference with LLM
- Used only for ambiguous cases.
- Examples: "reasonable dinner", "business necessity", "client meal", "good judgment".
- Benefits: handles real-world policy language and missing context.

### Rule for Deciding Layer
| Condition | Layer |
|---|---|
| Measurable | Structured rules |
| Needs interpretation | LLM |

Structured rules always run before the LLM.

---

## 7. Defended Choice: Open-Source LLM

- Choose self-hosted open-source models over third-party APIs.
- Keeps transaction data inside Reap's infrastructure.
- Eliminates per-token API costs at scale.
- Avoids vendor lock-in.
- Preserves the option to fine-tune on Reap's own policy and transaction data.
- Works well because the LLM is only used for ambiguous cases.
- The agent layer is provider-agnostic, so a model swap is a config change rather than a refactor.
- Closed models can remain optional fallback for difficult cases.

---

## 8. Decision Point Strategy

### Pre-Authorization
- Runs before purchase is approved.
- Best for hard blocks: banned vendors, banned categories, fraud-like patterns.
- **Pros**: prevents bad spend before it happens.
- **Cons**: strict latency, higher employee friction, false positives are painful.

### Post-Authorization Real Time
- Runs immediately after transaction approval.
- Best default for most policy checks.
- **Pros**: fast feedback without blocking purchase.
- **Cons**: spend may already have happened.

### Batch Sweep
- Runs periodically across many transactions.
- Best for audits, duplicate receipts, policy gaming, and repeated patterns.
- **Pros**: good for deeper analysis and lower cost.
- **Cons**: delayed feedback and slower recovery.

### Recommended Choice
- Use **post-authorization real time** as the main flow.
- Use **pre-authorization** only for simple high-confidence blocks.
- Use **batch sweeps** for pattern detection and audits.

---

## 9. Autonomy Model

### Agent Can Do Automatically
- Approve compliant transaction.
- Request receipt.
- Ask for clarification.
- Flag for review.
- Send employee message.

### Human Approval Required
- Clawback.
- Payroll deduction.
- Card suspension.
- HR/legal escalation.
- Any high-impact action based on ambiguous judgment.

---

## 10. Production-Ready Considerations

| Area | Detail |
|---|---|
| Policy versioning | Evaluate each transaction against the policy active at transaction time. |
| Human approval | Required before activating compiled policies. |
| Audit logs | Store policy version, rules checked, evidence, LLM usage, action, reviewer, and timestamp. |
| Explainability | Show why a transaction passed or failed. |
| Guardrails | LLM can advise, but high-stakes actions need review. |
| Monitoring | Track false positives, LLM usage, reviewer overrides, and recovery amount. |
| Security | Tenant isolation, role-based access, encrypted receipts, and restricted audit access. |
| Reliability | Deterministic rules should keep working even if LLM service is unavailable. |

---

## 11. Multi-Tenant Policy Versioning

This is one of the harder production problems in the design: policies change a few times a year, but transactions are evaluated in real time and re-examined in batch sweeps. The agent must always know exactly which version of a tenant's policy applied to a given transaction, and the answer must be consistent, auditable, and correct across all evaluation modes.

### 11.1 Policy Lifecycle

Every compiled policy moves through four states in order:

```
draft  →  approved  →  active  →  deprecated
```

| State | When it is set | Who sets it |
|---|---|---|
| `draft` | Immediately after LLM compilation | `policy_store.save_draft()` |
| `approved` | After human review signs off | `scripts/review_policy.py` (Phase 5.3) |
| `active` | When the policy is promoted for live evaluation | `policy_store.approve()` |
| `deprecated` | When a newer policy becomes active | `policy_store.approve()` (automatically) |

A policy that is `deprecated` is **never deleted**. It stays on disk so every past decision can be traced back to the exact rule set that produced it.

### 11.2 The One-Active-Policy Invariant

The central rule is: **exactly one policy can be `active` per tenant at any given moment — never zero, never two.**

This is enforced atomically inside `policy_store.approve()`:

```
1. Find the policy by ID, verify it is in draft (or approved) state.
2. For every existing policy for this tenant with status = active:
       → set status = deprecated, write to disk.
3. Set the target policy status = active, set approved_by + approved_at.
4. Write to disk and return.
```

Because step 2 runs before step 3 in a single synchronous function call, there is never a moment where two policies are simultaneously active, and the window between deprecating the old one and activating the new one is sub-millisecond.

### 11.3 Version Assignment

Version numbers are sequential integers per tenant. The compiler itself is version-agnostic — it always produces `version=1` in its output. The store owns numbering:

```python
# policy_store.save_draft()
next_version = max(p.version for p in existing_versions, default=0) + 1
```

This means:
- First policy for a tenant: version 1.
- Each subsequent compiled policy for that tenant: version N+1.
- The version number in a `CompiledPolicy` is the authoritative identifier for a specific rule set, independent of the `policy_id` UUID.

### 11.4 Which Policy Version Applies to a Transaction?

#### Real-time evaluation (post-authorization)

The agent calls `policy_store.get_active(tenant_id)` at evaluation time. Because evaluation happens within seconds of the transaction, the active policy at evaluation time is the same as the active policy at transaction time. No ambiguity.

#### Batch sweeps

Batch sweeps re-examine transactions that have already settled, possibly days or weeks later, after the policy may have changed. Two defensible approaches exist:

| Approach | Behaviour | When to use |
|---|---|---|
| **Evaluation-time policy** (our default) | Re-evaluate against the policy that is currently active. New rules apply retroactively. | Audit sweeps where the goal is "does this spend comply with our current rules?" |
| **Transaction-time policy** | Retrieve the policy version that was active at the transaction timestamp. Use `list_versions()` + `approved_at` to reconstruct it. | Dispute resolution, clawback proposals, anything where the employee's obligation should be judged by what they were told at the time. |

Our implementation defaults to evaluation-time because it is simpler and the common audit case. Transaction-time reconstruction is available as a fallback: `policy_store.list_versions(tenant_id)` returns all versions with their `created_at` and `approved_at` timestamps, so the caller can binary-search for the version that was active at any historical moment.

### 11.5 Audit Trail

Every `Decision` record stores `policy_version: int` — the version number that was used when the decision was made. This field is written at evaluation time and never changed. It means:

- Finance can always ask "why was this transaction flagged?" and get a precise answer: "Rule `rule-003` in policy version 4 fired because the hotel rate was $320 against a $250 cap."
- If a policy is later updated to raise the cap to $350, the historical decision still references version 4 and still shows the correct reason.
- The audit log is append-only and policy-version-stamped, so the record is always accurate regardless of how many policy updates follow.

### 11.6 Storage Layout

```
mcp_server/data/policies/
└── {tenant_id}/
    ├── {policy_id_A}.txt              ← raw natural language upload
    ├── {policy_id_A}.compiled.json    ← compiled + versioned policy (draft / approved / active / deprecated)
    ├── {policy_id_B}.txt
    └── {policy_id_B}.compiled.json
```

Each `.compiled.json` file is a self-contained `CompiledPolicy` blob. The status field inside the file is the source of truth. `policy_store` functions read, update, and write these files; no separate index or registry is maintained.

### 11.7 Service API Summary

| Function | Signature | What it does |
|---|---|---|
| `save_draft` | `(compiled_policy) → policy_id` | Assigns next version, forces status=draft, writes to disk |
| `approve` | `(policy_id, reviewer_id) → CompiledPolicy` | draft → active; deprecates previous active |
| `get_active` | `(tenant_id) → CompiledPolicy \| None` | Returns the single active policy, or None |
| `get_version` | `(tenant_id, version) → CompiledPolicy \| None` | Retrieves a specific historical version |
| `list_versions` | `(tenant_id) → list[CompiledPolicy]` | All versions sorted ascending — used for transaction-time reconstruction |

### 11.8 Implemented Tools and Evaluation Paths

**MCP read tools**

- `get_active_policy(tenant_id)` in `mcp_server/tools/read_tools.py` returns `policy_store.get_active(tenant_id)` as JSON.
- The active compiled policy lives under `mcp_server/data/policies/{tenant_id}/{policy_id}.compiled.json`.
- Current Meru active policy: `meru-inc` version 4, status `active`.

**Non-LLM structured path**

Used first for deterministic predicates in `backend/app/services/rule_engine.py`.

Examples: `amount_requires_receipt`, `amount_cap`, `vendor_blocklist`, `vendor_allowlist`, `mcc_ban`, `hotel_star_max`, `per_diem_cap`, `category_pre_approval`, `requires_attendee_note`.

Returns:

```text
(verdict, rules_fired, missing_evidence)
```

Example: `$120 USD` with no receipt against a `$75 USD` receipt rule returns `needs_evidence`.

**LLM path**

Used only after structured checks cannot fully decide the case.

Examples:
- Alcohol reimbursable only when clients are present.
- "Reasonable" or "good judgment" spend.
- Client dinner context requiring calendar/receipt interpretation.

The LLM uses `NaturalLanguageReference` clauses plus transaction context. Clear numeric/list rules stay on the non-LLM path.

---

## 12. Minimal Demo Output

**Input**
- Transaction: $320 USD hotel charge.
- Policy: hotel cap is $250 USD unless manager approval exists.

**Output**
- **Status**: Non-compliant.
- **Reason**: Amount exceeds hotel cap.
- **Action**: Escalate for manager approval.
- **Employee message**: *"Your hotel transaction exceeds the $250 USD cap. Please provide manager approval or business justification."*
- **Audit**: policy version, rule matched, evidence, timestamp.

---

## 13. Final Position

- Build the agent workflow first.
- Use hybrid policy representation.
- Run structured rules before LLM.
- Prefer open-source LLMs for ambiguous cases.
- Use post-authorization real-time checks as the main decision point.
- Keep high-stakes actions under human approval.
- Make every decision explainable, versioned, and auditable.

---

## 14. Data Schemas (`backend/app/schemas.py`)

All data contracts are defined as Pydantic v2 models. Every field is typed and validated at the boundary.

| Model | What it represents |
|---|---|
| `Transaction` | A single card spend event submitted for evaluation |
| `Employee` | Staff member who initiated the transaction |
| `Vendor` | Known merchant in the tenant's vendor master, with blocklist flag |
| `Receipt` / `ReceiptLineItem` | OCR'd receipt and its itemised lines attached as evidence |
| `CompiledRule` | One machine-executable rule extracted from natural language policy |
| `NaturalLanguageReference` | Policy clause kept as text for LLM judgment on ambiguous cases |
| `UnsupportedClause` | Clause the compiler could not convert to a structured rule |
| `CompiledPolicy` | A versioned, approved policy with structured rules and NL references |
| `Decision` | Final agent output: verdict, action, rule path, confidence, rationale |
| `AuditEntry` | Immutable record of one pipeline step with inputs and outputs |

**Enums**

- `PredicateType` — the kind of check a rule performs (e.g. `amount_cap`, `vendor_blocklist`, `per_diem_cap`).
- `ActionType` — what the agent does on a result (e.g. `block`, `flag`, `escalate`, `propose_clawback`).
- `PolicyStatus` — lifecycle of a compiled policy (`draft → approved → active → deprecated`).
- `Verdict` — outcome of evaluating a transaction (`pass_through`, `fail`, `needs_evidence`, `needs_judgment`, `abstain`).

---

## 15. Mock Data (`mcp_server/data/`)

Tenant: **Meru Inc** (`meru-inc`). All files are JSON and served by the MCP server. In production these are replaced by live Reap API calls.

### Employees — 5 records
| ID | Name | Dept | Country | Level |
|---|---|---|---|---|
| emp-001 | Alice Chen | Sales | US | Manager |
| emp-002 | Ben Williams | Engineering | GB | IC3 |
| emp-003 | Leila Nasser | Marketing | SG | IC2 |
| emp-004 | Tom Hargreaves | Sales | GB | IC4 |
| emp-005 | Sarah Kim | Engineering | US | Director |

### Vendors — 15 records (2 blocklisted)
13 allowed vendors across Hotels, Transport, Travel, Software, and Restaurants. Blocklisted: **Competitor Corp** and **RivalCo**. Hotel vendors carry a `star_rating` field used by the hotel star rule.

### Transactions — 10 records
| ID | Employee | Amount | Scenario |
|---|---|---|---|
| txn-001 | emp-001 | $220 USD | Compliant hotel — 4-star, under NYC cap, receipt attached |
| txn-002 | emp-002 | $299 USD | Compliant SaaS — under $500 pre-approval threshold |
| txn-003 | emp-003 | SGD 42 | Compliant transport — under receipt threshold |
| txn-004 | emp-004 | $580 USD | Compliant flight — receipt attached |
| txn-005 | emp-005 | $68 USD | Compliant solo lunch — receipt attached |
| txn-006 | emp-001 | $180 USD | **Fail** — over $75 receipt threshold, no receipt |
| txn-007 | emp-002 | $500 USD | **Fail** — Competitor Corp is blocklisted |
| txn-008 | emp-003 | $320 USD | **Ambiguous** — solo overspend or compliant client dinner for 3? |
| txn-009 | emp-004 | $450 USD | **Fail** — 5-star hotel, exceeds star limit and $250 NYC cap |
| txn-010 | emp-005 | $1200 USD | **Fail** — SaaS above $500/month, no pre-approval on record |

### Receipts — 3 records
Attached to txn-001 (hotel), txn-004 (flight), txn-005 (lunch). txn-006 through txn-010 are intentionally missing receipts where noted.

### Calendar — keyed by employee_id
Used to resolve the ambiguous txn-008: emp-003 has a confirmed client dinner event (`is_client_meeting: true`) on 2026-05-14 19:00 overlapping the transaction, which the judgment agent can use as supporting evidence.

### Policy — `policies/Meru_v1.txt`
8 natural-language clauses covering: receipt threshold ($75), hotel star limit and nightly caps (NYC/London $250, Singapore SGD 200), client dinner reimbursement ($150/person), alcohol rule, SaaS pre-approval ($500/month), vendor blocklist, team entertainment, and quarterly board reporting.

---

## Production-Ready End Note

- **MVP runs locally**: Next.js frontend, FastAPI backend, MCP server, and Ollama serving Qwen 2.5 7B.
- One command should give the reviewer a working demo with no API costs and no cloud setup.
- For production, the same code can run on AWS without major changes:
  - Backend and MCP server deploy as AWS Lambda functions behind API Gateway.
  - LLM endpoint moves from local Ollama to a managed inference API (Hugging Face Endpoints, Together AI, or AWS Bedrock).
  - File-based mocks move to Postgres on RDS.
  - Audit logs move to S3 or a dedicated append-only audit table.
- This works because the architecture is **deployment-agnostic**:
  - The LLM is reached through an OpenAI-compatible client, so the model can be swapped with a config change.
  - Storage is behind a simple interface, so the database can be swapped the same way.
