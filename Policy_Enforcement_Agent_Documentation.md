# Workflow 2 — Policy Enforcement Agent

## Three Important Evaluation Areas

1. **Product thinking**: what problem we solve, for whom, and what actions the agent should take.
2. **Architecture and technology choices**: how policies, rules, LLMs, receipts, and actions work together.
3. **Production-ready solution**: how the system handles safety, auditability, versioning, scale, and human review.

---

## Product Context

**Why this workflow:**

- **Biggest financial impact.** Roughly 5% of customer spend goes out of policy and most of it is never recovered. A policy enforcement agent addresses this directly, saving real money every month, not just reducing close-time overhead.
- **Cuts across all of Reap.** Card spend, bill pay, and Optimize all involve money that must follow rules. A policy agent is the right foundation for the AI CFO vision; it is not a narrow feature but a core primitive.
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

## 3. Key Assumptions

**Scope**
- Core agent only: not a full finance platform.
- Policies are natural-language text uploaded by the customer. PDF/Word OCR is future work.

**Data**
- Reap supplies transaction events, OCR'd receipts, vendor records, employee profiles, and per-tenant chart of accounts. These are mocked in the demo but the data model is multi-tenant throughout.
- Receipts are represented as structured parsed data, not raw images or PDFs.
- Policies change a few times per year; real-time sync is not a requirement.

**Actions**
- Real blocking, clawback, and payroll deduction are not executed. The agent proposes actions and generates employee-facing messages; a human operator carries them out.
- High-stakes actions (clawback, suspension) are queued for human approval and never auto-executed.

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

### Why not LLM-only?

LLMs are non-deterministic: the same transaction can get different verdicts on different runs, with no audit trail showing which rule fired. Finance teams must be able to explain every flag; "the model thought it was non-compliant" is not defensible.

### Why not rules-only?

Policies contain clauses like "alcohol is reimbursable only when clients are present." No finite rule set can encode contextual intent: identical amounts can be compliant or non-compliant depending on who was present. Rules alone produce false positives on legitimate spend and false negatives on violations buried in ambiguous language.

### The hybrid model

| Policy clause type         | Layer              | Examples                                               |
| -------------------------- | ------------------ | ------------------------------------------------------ |
| Measurable threshold       | Structured rule    | `amount > $75 → receipt required`                   |
| Categorical ban            | Structured rule    | `vendor in [Competitor Corp] → block`               |
| Conditional interpretation | NL reference + LLM | "clients present", "reasonable", "good judgment"       |
| Context-dependent          | NL reference + LLM | Attendee list, calendar cross-check, purpose statement |

**Implementation:**

1. At compile time, the LLM reads the natural-language policy and emits two artefacts: (a) structured `CompiledRule` objects for anything measurable, and (b) `NaturalLanguageReference` entries for clauses it could not convert. Unsupported clauses are flagged explicitly.
2. At evaluation time, structured rules run first: deterministic, fast, auditable. If the result is unambiguous (pass or fail), the LLM is never invoked.
3. Only when structured rules return `needs_judgment` does the LLM run, with the relevant NL references injected into its system prompt.

This means the LLM is a fallback, not the primary evaluator. Deterministic accuracy stays at 100% for measurable cases; LLM adds judgment for the remainder.

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

The three evaluation windows differ sharply on latency, cost, and the cost of a false positive. The choice is not binary; all three are used at different points in the pipeline.

|                               | Pre-authorization                                                                                          | Post-authorization real time                                      | Batch sweep                                                                |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | -------------------------------------------------------------------------- |
| **When it runs**        | Before card approves                                                                                       | Within seconds of approval                                        | Hours or days later                                                        |
| **Latency budget**      | <200 ms (synchronous)                                                                                      | 2–5 s acceptable                                                 | Minutes to hours                                                           |
| **Compute cost**        | High (every swipe)                                                                                         | Moderate (most swipes)                                            | Low per-transaction (parallelised)                                         |
| **False positive cost** | **Very high**: blocks a legitimate purchase at point of sale; employee is embarrassed and loses time | Medium: employee gets a notification after the fact; recoverable  | Low: employee has days to respond                                          |
| **False negative cost** | Low: post-auth sweep catches it                                                                            | Medium: spend has occurred but recovery is still fast             | High: money may be settled and harder to recover                           |
| **Best for**            | Hard bans: blocklisted vendors, MCC bans, card-level fraud signals                                         | Receipt requests, amount caps, category checks, hotel star limits | Structuring patterns, duplicate receipts, policy-change retroactive sweeps |

### Consequences of getting pre-authorization wrong

A pre-auth false positive blocks a purchase at point of sale, embarrassing the employee and damaging client trust. Checks here must be <200 ms and high-precision, limiting them to blocklist, MCC ban, and card-level lookups. A post-auth false positive sends an unnecessary evidence request; recoverable, since the purchase already went through.

### Recommended architecture

- **Pre-authorization**: structured rules only, no LLM, <200 ms. Scoped to hard bans and card-level blocks.
- **Post-authorization real time**: full pipeline (structured rules + LLM fallback). This is the main evaluation path used in this build.
- **Batch sweep**: re-run structured rules across a time window to detect patterns (structuring, duplicate receipts). LLM is not run per-transaction in batch; it is used only to summarise flagged clusters for a human reviewer.

---

## 9. Autonomy Model

The core design principle is: **the agent's autonomy is proportional to the reversibility of the action**. Actions that can be undone cheaply are automated; actions that are hard to reverse or carry legal/employment risk require a human to approve.

### Agent acts automatically

| Action                     | Reversible?                   | Why auto                                          |
| -------------------------- | ----------------------------- | ------------------------------------------------- |
| Mark transaction compliant | Yes, can be revisited         | Low risk; no employee impact                      |
| Request receipt / evidence | Yes, request can be withdrawn | Employee expects this; no harm if wrong           |
| Flag for finance review    | Yes, reviewer can dismiss    | Surfaces problem without acting on it             |
| Send employee notification | Partially                     | Fast feedback; tone is informational not punitive |

### Human approval required

| Action                       | Why human must approve                                                                           |
| ---------------------------- | ------------------------------------------------------------------------------------------------ |
| Clawback / payroll deduction | Irreversible financial impact on employee; employment law in most jurisdictions requires process |
| Card suspension              | Blocks all spend; high operational disruption if wrong                                           |
| HR/legal escalation          | Creates a formal record; cannot be easily retracted                                              |
| Block at pre-authorization   | Embarrasses employee at point of sale; false positive is costly                                  |

### Why clawback is particularly sensitive

Clawback is the highest-risk action in the pipeline for three reasons:

1. **Employment law**: deducting from salary requires written consent or a formal dispute process; automated execution creates legal liability even if the spend was genuinely out of policy.
2. **Irreversibility**: re-paying an erroneous deduction requires a separate payroll cycle, causing real financial harm to the employee.
3. **Confidence threshold**: a model at 90% confidence should flag, not execute; only a human who has reviewed the evidence and heard the employee's response should authorise a clawback.

**Implementation guard:** the agent never executes a clawback directly. Instead, it calls `propose_high_stakes_action`, which queues a proposal in `human_approval_queue.jsonl` with `status=pending_human_approval` and waits for a human to act. This is enforced by a hard rule in the judgment agent's system prompt: *"NEVER auto-execute block or clawback — always use propose_high_stakes_action."*

---

## 10. Receipt Parsing and Transaction Matching

Receipts are the primary evidence that a transaction is policy-compliant. The pipeline needs to answer two questions for every receipt: is this receipt genuine, and does it belong to this transaction?

### Ingestion

In production, Reap already provides OCR-processed receipts via its existing infrastructure. The agent does not need to perform OCR itself; it receives structured receipt data: line items with names and amounts, total, currency, merchant name, and optionally attendees and business purpose.

In this build, receipts are pre-parsed JSON records in `mcp_server/data/receipts.json`. The same data model is used so the switch to live OCR is a datasource swap, not a schema change.

### Matching a receipt to a transaction

A receipt is matched to a transaction on `transaction_id` as the primary key. In production, a secondary fuzzy match is needed because the receipt `transaction_id` may not always be present (e.g. a receipt uploaded by an employee after the fact). The fallback matching strategy:

| Signal                      | Weight                                |
| --------------------------- | ------------------------------------- |
| Amount match (within ±5%)  | High                                  |
| Merchant name similarity    | High                                  |
| Timestamp proximity (±24h) | Medium                                |
| Currency match              | Medium                                |
| Employee ID                 | Low (one employee, many transactions) |

A receipt that matches on amount + merchant + timestamp is considered attached. A receipt where any of these diverge by more than the tolerance is flagged for manual review rather than silently linked.

### Line-item analysis

Once matched, the agent reads line items to apply specific policy rules:

- **Alcohol rule**: if any line item is categorised as `Alcohol` and no attendee list is present, the NL reference "alcohol is reimbursable only when clients are present" applies. The structured rule engine cannot catch this alone; it requires the LLM to interpret the receipt content against the policy clause.
- **Attendee note**: if the policy requires an attendee list and `receipt.attendees` is null, the `requires_attendee_note` predicate fires and returns `needs_evidence`.
- **Amount cap**: `receipt.total_amount` is compared against the transaction amount. A significant discrepancy (>10%) triggers a flag even if both are individually within policy.

### Known gap: alcohol line item without a structured rule

The current demo policy does not include a `requires_attendee_note` rule for meal transactions. The eval harness (Phase 14) deliberately includes a receipt with alcohol line items and no attendee note, and correctly catches this as a **false negative** (verdict `pass_through` when `needs_judgment` is expected). Fixing it requires adding a `requires_attendee_note` structured rule scoped to meal MCC codes. This is the clearest example of a policy gap that the eval harness surfaces.

---

## 10b. Adversarial Users and Policy Gaming

A policy enforcement system that employees know exists creates an incentive to game it. The brief explicitly calls out structuring as an example. This section catalogues the known attack patterns and our mitigations.

### Structuring (splitting spend under caps)

**Pattern:** Three dinners at $149, $148, $147 on consecutive days, each just under a $150 cap, collectively $444 in a week.

**Current behaviour:** Each triggers `needs_evidence` individually (amount > $75, no receipt). With receipts attached, each passes. The aggregate pattern is invisible to a per-transaction engine.

**Mitigation (planned):** A nightly batch job aggregates spend by employee × merchant × category × rolling 7-day window and flags clusters that exceed a configurable threshold even if each transaction passed individually. Out of MVP scope; the eval harness notes this gap explicitly.

### Vendor name typos to evade the blocklist

**Pattern:** "Cmpetitor Corp" (one-character typo of blocked "Competitor Corp") passes exact-match blocklist check.

**Current behaviour:** Rule engine compares `txn.merchant_name.lower()` exactly; no match, rule does not fire. Transaction returns `needs_evidence` on the receipt rule, not `fail`. Confirmed as a `GAP` in the Phase 14 eval (`txn-0015`).

**Mitigation (planned):** Fuzzy matching using Levenshtein distance ≤ 2 on `merchant_name`. Near-matches return `needs_judgment` instead of passing silently. The blocklist is a plain string list; swapping in a similarity function requires no schema change.

### Category misclassification

**Pattern:** Personal electronics submitted under MCC 5812 (restaurants) to avoid a category ban.

**Mitigation:** MCC is set by the card network at authorisation and cannot be changed by the employee. The agent checks MCC directly via the `mcc_ban` predicate; vendor category provides a secondary cross-check.

### Receipt fabrication or alteration

**Pattern:** Fabricated or edited receipt submitted to justify spend that did not occur or was overstated.

**Mitigation:** Receipts should be ingested from Reap's existing OCR pipeline rather than accepted as raw employee uploads. OCR confidence scores flag low-quality or digitally-created images. High-value transactions require finance review of the receipt regardless of automated verdict. This is a platform-level control; the policy agent alone cannot enforce it.

### Summary of mitigations

| Attack                                | Current status                        | Planned fix                           |
| ------------------------------------- | ------------------------------------- | ------------------------------------- |
| Structuring under per-transaction cap | Caught individually; pattern missed   | Batch sweep on rolling window         |
| Vendor name typo evading blocklist    | Missed (GAP in eval)                  | Fuzzy vendor matching (edit distance) |
| Category misclassification            | Caught via MCC (card network sets it) | Already implemented                   |
| Receipt fabrication                   | Caught only if OCR pipeline flags it  | Platform-level image verification     |

---

| Area              | Detail                                                                                     |
| ----------------- | ------------------------------------------------------------------------------------------ |
| Policy versioning | Evaluate each transaction against the policy active at transaction time.                   |
| Human approval    | Required before activating compiled policies.                                              |
| Audit logs        | Store policy version, rules checked, evidence, LLM usage, action, reviewer, and timestamp. |
| Explainability    | Show why a transaction passed or failed.                                                   |
| Guardrails        | LLM can advise, but high-stakes actions need review.                                       |
| Monitoring        | Track false positives, LLM usage, reviewer overrides, and recovery amount.                 |
| Security          | Tenant isolation, role-based access, encrypted receipts, and restricted audit access.      |
| Reliability       | Deterministic rules should keep working even if LLM service is unavailable.                |

---

## 11. Multi-Tenant Policy Versioning

This is one of the harder production problems in the design: policies change a few times a year, but transactions are evaluated in real time and re-examined in batch sweeps. The agent must always know exactly which version of a tenant's policy applied to a given transaction, and the answer must be consistent, auditable, and correct across all evaluation modes.

### 11.1 Policy Lifecycle

Every compiled policy moves through four states in order:

```
draft  →  approved  →  active  →  deprecated
```

| State          | When it is set                                  | Who sets it                                |
| -------------- | ----------------------------------------------- | ------------------------------------------ |
| `draft`      | Immediately after LLM compilation               | `policy_store.save_draft()`              |
| `approved`   | After human review signs off                    | `scripts/review_policy.py` (Phase 5.3)   |
| `active`     | When the policy is promoted for live evaluation | `policy_store.approve()`                 |
| `deprecated` | When a newer policy becomes active              | `policy_store.approve()` (automatically) |

A policy that is `deprecated` is **never deleted**. It stays on disk so every past decision can be traced back to the exact rule set that produced it.

### 11.2 The One-Active-Policy Invariant

The central rule is: **exactly one policy can be `active` per tenant at any given moment (never zero, never two).**

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

Version numbers are sequential integers per tenant. The compiler itself is version-agnostic; it always produces `version=1` in its output. The store owns numbering:

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

| Approach                                       | Behaviour                                                                                                                              | When to use                                                                                                                           |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| **Evaluation-time policy** (our default) | Re-evaluate against the policy that is currently active. New rules apply retroactively.                                                | Audit sweeps where the goal is "does this spend comply with our current rules?"                                                       |
| **Transaction-time policy**              | Retrieve the policy version that was active at the transaction timestamp. Use `list_versions()` + `approved_at` to reconstruct it. | Dispute resolution, clawback proposals, anything where the employee's obligation should be judged by what they were told at the time. |

Our implementation defaults to evaluation-time because it is simpler and the common audit case. Transaction-time reconstruction is available as a fallback: `policy_store.list_versions(tenant_id)` returns all versions with their `created_at` and `approved_at` timestamps, so the caller can binary-search for the version that was active at any historical moment.

### 11.5 Audit Trail

Every `Decision` record stores `policy_version: int`, the version number that was used when the decision was made. This field is written at evaluation time and never changed. It means:

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

| Function          | Signature                                         | What it does                                                              |
| ----------------- | ------------------------------------------------- | ------------------------------------------------------------------------- |
| `save_draft`    | `(compiled_policy) → policy_id`                | Assigns next version, forces status=draft, writes to disk                 |
| `approve`       | `(policy_id, reviewer_id) → CompiledPolicy`    | draft → active; deprecates previous active                               |
| `get_active`    | `(tenant_id) → CompiledPolicy \| None`          | Returns the single active policy, or None                                 |
| `get_version`   | `(tenant_id, version) → CompiledPolicy \| None` | Retrieves a specific historical version                                   |
| `list_versions` | `(tenant_id) → list[CompiledPolicy]`           | All versions sorted ascending; used for transaction-time reconstruction |

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

| Model                             | What it represents                                                    |
| --------------------------------- | --------------------------------------------------------------------- |
| `Transaction`                   | A single card spend event submitted for evaluation                    |
| `Employee`                      | Staff member who initiated the transaction                            |
| `Vendor`                        | Known merchant in the tenant's vendor master, with blocklist flag     |
| `Receipt` / `ReceiptLineItem` | OCR'd receipt and its itemised lines attached as evidence             |
| `CompiledRule`                  | One machine-executable rule extracted from natural language policy    |
| `NaturalLanguageReference`      | Policy clause kept as text for LLM judgment on ambiguous cases        |
| `UnsupportedClause`             | Clause the compiler could not convert to a structured rule            |
| `CompiledPolicy`                | A versioned, approved policy with structured rules and NL references  |
| `Decision`                      | Final agent output: verdict, action, rule path, confidence, rationale |
| `AuditEntry`                    | Immutable record of one pipeline step with inputs and outputs         |

**Enums**

- `PredicateType`: the kind of check a rule performs (e.g. `amount_cap`, `vendor_blocklist`, `per_diem_cap`).
- `ActionType`: what the agent does on a result (e.g. `block`, `flag`, `escalate`, `propose_clawback`).
- `PolicyStatus`: lifecycle of a compiled policy (`draft → approved → active → deprecated`).
- `Verdict`: outcome of evaluating a transaction (`pass_through`, `fail`, `needs_evidence`, `needs_judgment`, `abstain`).

---

## 15. Mock Data (`mcp_server/data/`)

Tenant: **Meru Inc** (`meru-inc`). All files are JSON and served by the MCP server. In production these are replaced by live Reap API calls.

### Employees — 5 records

| ID      | Name           | Dept        | Country | Level    |
| ------- | -------------- | ----------- | ------- | -------- |
| emp-001 | Alice Chen     | Sales       | US      | Manager  |
| emp-002 | Ben Williams   | Engineering | GB      | IC3      |
| emp-003 | Leila Nasser   | Marketing   | SG      | IC2      |
| emp-004 | Tom Hargreaves | Sales       | GB      | IC4      |
| emp-005 | Sarah Kim      | Engineering | US      | Director |

### Vendors — 16 records (2 blocklisted)

14 allowed vendors across Hotels, Transport, Travel, Software, and Restaurants. Blocklisted: **Competitor Corp** and **RivalCo**. Hotel vendors carry a `star_rating` field used by the hotel star rule. **Cmpetitor Corp** (`vnd-016`) is included as a Phase 14 adversarial case: a one-character typo of the blocked vendor, not on the blocklist and not caught by exact matching.

### Transactions — 16 records

| ID      | Employee | Amount                                                                        | Scenario                                                                               |
| ------- | -------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| txn-001 | emp-001 | $220 USD  | Compliant hotel, 4-star, receipt attached; judgment agent handles star check |
| txn-002 | emp-002 | $299 USD  | Needs evidence: SaaS $299, no receipt, above $75 threshold |
| txn-003 | emp-003 | SGD 42    | Compliant transport: SGD 42 ≈ USD 31, under receipt threshold |
| txn-004 | emp-004 | $580 USD  | Compliant flight, receipt attached |
| txn-005 | emp-005 | $68 USD   | Compliant solo lunch, under $75 threshold, receipt attached |
| txn-006 | emp-001 | $180 USD  | **Fail**: over $75 receipt threshold, no receipt |
| txn-007 | emp-002 | $500 USD  | **Fail**: Competitor Corp is blocklisted |
| txn-008 | emp-003 | $320 USD  | **Ambiguous**: solo overspend or compliant client dinner for 3? |
| txn-009 | emp-004 | $450 USD  | **Fail**: 5-star hotel, no receipt, needs evidence |
| txn-010 | emp-005 | $1200 USD | **Fail**: SaaS above $500/month, no pre-approval on record |
| txn-011 | emp-001 | $149 USD  | **Phase 14**: structuring day 1, no receipt |
| txn-012 | emp-001 | $148 USD  | **Phase 14**: structuring day 2, no receipt |
| txn-013 | emp-001 | $147 USD  | **Phase 14**: structuring day 3, no receipt |
| txn-014 | emp-003 | $95 USD   | **Phase 14**: receipt with alcohol line items, no attendee note (known gap) |
| txn-015 | emp-002 | $500 USD  | **Phase 14**: typo vendor "Cmpetitor Corp", not caught by blocklist |
| txn-016 | emp-005 | €70 EUR   | **Phase 14**: EUR transaction, 70 EUR ≈ USD 76, crosses $75 receipt threshold |

### Receipts — 4 records

Attached to txn-001 (hotel), txn-004 (flight), txn-005 (lunch), and txn-014 (client dinner with alcohol line items, the adversarial receipt). txn-002, txn-006 through txn-010, and txn-011 through txn-013 are intentionally missing receipts.

### Calendar — keyed by employee_id

Used to resolve the ambiguous txn-008: emp-003 has a confirmed client dinner event (`is_client_meeting: true`) on 2026-05-14 19:00 overlapping the transaction, which the judgment agent can use as supporting evidence.

### Policy — active compiled policy (version 5, `dddddddd-...`)

4 structured rules: receipt required above $75, hotel star max 4, vendor blocklist (Competitor Corp / RivalCo → block), SaaS pre-approval above $500/month (→ escalate). Plus 1 natural-language reference for alcohol/client-presence clause and 1 unsupported clause (quarterly board report obligation).

---

## Production-Ready End Note

The MVP runs entirely on a laptop: Next.js frontend, FastAPI backend, MCP server, and Ollama serving Qwen 2.5 7B. One command gives a reviewer a working demo with no API costs and no cloud setup.

The same code moves to production without major changes because the architecture is deployment-agnostic:

| Component   | MVP (local)            | Production (AWS)                                     |
| ----------- | ---------------------- | ---------------------------------------------------- |
| Backend     | FastAPI + uvicorn      | AWS Lambda behind API Gateway                        |
| LLM         | Ollama (Qwen 2.5 7B)   | Managed inference (HuggingFace, Together AI, Bedrock) |
| Storage     | JSON flat files        | Postgres on RDS                                      |
| Audit log   | Append-only JSONL      | S3 or dedicated append-only audit table              |

The LLM is reached through an OpenAI-compatible client, so the model is a config change. Storage sits behind a simple interface, so the database is a config change too.
