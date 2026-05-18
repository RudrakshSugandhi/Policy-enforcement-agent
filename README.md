# Reap Policy Enforcement Agent

An AI-powered expense policy enforcement system. Upload a plain-text policy, compile it into structured rules via LLM, then evaluate transactions against it — deterministically or via LLM judgment.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Complete Workflow](#complete-workflow)
4. [Test Data — Policy Text](#test-data--policy-text)
5. [Test Data — Transactions](#test-data--transactions)
6. [Test Data — Custom Upload JSONs](#test-data--custom-upload-jsons)
7. [Test Data — Receipt Submission](#test-data--receipt-submission)
8. [Architecture](#architecture)
9. [API Reference](#api-reference)
10. [Environment Variables](#environment-variables)

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | ≥ 3.11 | Backend runtime |
| Conda | any | Virtual environment |
| Node.js | ≥ 18 | Frontend runtime |
| Ollama | latest | Local LLM server |

### Install Ollama and pull the model

```bash
# Install Ollama from https://ollama.com
ollama pull qwen2.5:7b-instruct
```

---

## Quick Start

### 1 — Backend

```bash
# From reap-policy-agent/
conda activate reap-policy-agent
pip install -e backend/
uvicorn backend.app.api:app --reload --port 8000
```

Backend runs at `http://localhost:8000`  
Interactive docs at `http://localhost:8000/docs`

![Backend API docs](Application%20Screenshots/Screenshot%202026-05-18%20at%204.35.31%E2%80%AFPM.png)

### 2 — Frontend

```bash
# From reap-policy-agent/frontend/
npm install
npm run dev
```

Frontend runs at `http://localhost:3000`

![Application frontend](Application%20Screenshots/Screenshot%202026-05-18%20at%204.36.51%E2%80%AFPM.png)

> Both services must be running at the same time. Keep two terminal tabs open.

---

## Complete Workflow

The application has three connected stages.

---

### Stage 1 — Create & Approve a Policy

**Go to:** `http://localhost:3000/policy/create`

1. Paste policy text into the editor **or** switch to **Upload mode** and drop a `.txt` file.
2. Set the **Tenant ID** to `meru-inc` (pre-filled by default).
3. Click **Compile policy** — the LLM extracts:
   - **Structured rules** — measurable checks (amount caps, vendor blocklists, star limits, pre-approval thresholds)
   - **Natural language references** — clauses requiring human judgment (e.g. "clients must be present")
   - **Unsupported clauses** — governance obligations not enforceable at transaction level
4. You are redirected to the **Review** page showing the compiled output.
5. Click **Approve policy** — the policy becomes active; the previous version is automatically deprecated.
6. Click **Reject** — returns to the create page to revise the text.

> Only one policy can be active per tenant at a time.

<!-- screenshot: policy/create page -->

&nbsp;

<!-- screenshot: policy/review page showing compiled rules -->

&nbsp;

---

### Stage 2 — Evaluate Transactions

**Go to:** `http://localhost:3000/evaluate`

#### Tab A — Stored Transactions

1. Select a transaction from the dropdown. The preview card shows employee, department, amount, merchant, and MCC code.
2. Click **Evaluate** — the backend runs the rule engine against the active policy.
3. The result panel shows:
   - **Verdict badge** — `pass_through` / `fail` / `needs_evidence` / `needs_judgment` / `abstain`
   - **Action taken** — `pass_through` / `block` / `flag` / `request_evidence` / `escalate` / `propose_clawback`
   - **Rules violated** — each fired rule shown as a named card with the source policy clause and predicate label
   - **LLM judgment badge** — shown when the judgment agent was invoked
   - **LLM rationale** — natural-language explanation when the agent was used
   - **Confidence score** — 0.0 (uncertain) to 1.0 (fully deterministic)

#### Tab B — Upload JSON

1. Drop a `.json` file onto the upload area, or click to browse.
2. A preview of the parsed transaction is shown before submission.
3. Click **Evaluate** — same result panel as Tab A.
4. Download `sample-transaction.json` (button on the tab) for a pre-built example that triggers LLM judgment.

#### Receipt Submission

When the verdict is `needs_evidence`, a **Submit Receipt** form appears below the result:

1. Enter the receipt total, currency, business purpose, and optional attendees (comma-separated).
2. Click **Submit receipt & re-evaluate** — the receipt is saved and the transaction is immediately re-evaluated.
3. The verdict updates in place (typically changes to `pass_through` once the receipt is on file).

<!-- screenshot: evaluate page — verdict panel and receipt form -->

&nbsp;

---

### Stage 3 — Dashboard

**Go to:** `http://localhost:3000`

- **Stat cards** — total evaluated, passed, failed, needs-review counts
- **Recent decisions table** — latest 10 evaluations with verdict, action, and **LLM judgment** badge for agent-assisted rows
- Click **View** on any row to open the full decision detail and audit trail
- Click **Refresh** to reload the feed after new evaluations

<!-- screenshot: dashboard with stat cards and recent decisions table -->

&nbsp;

---

## Test Data — Policy Text

Paste this into the policy editor (or save as a `.txt` file and upload):

```
Meru Inc — Employee Expense Policy

1. Receipts are required for any expense over 75 USD.

2. Hotels must be four stars or below.

3. Purchases from Competitor Corp and RivalCo are not permitted.

4. SaaS subscriptions above 500 USD per month require pre-approval from the department head before purchase.

5. Alcohol is reimbursable only when clients are present and must not exceed 20% of the total bill.

6. Quarterly expense reports must be submitted to the board.
```

**Expected compilation output:**

| Rule | Predicate | Action |
|------|-----------|--------|
| rule-001 | `amount_requires_receipt` (threshold: $75) | `request_evidence` |
| rule-002 | `hotel_star_max` (max: 4 stars) | `flag` |
| rule-003 | `vendor_blocklist` (Competitor Corp, RivalCo) | `block` |
| rule-004 | `category_pre_approval` (SaaS > $500/mo) | `escalate` |
| NL ref | Alcohol clause (clients present, ≤ 20%) | LLM judgment |
| Unsupported | Quarterly board reporting | Not enforceable at transaction level |

---

## Test Data — Transactions

The system has 16 pre-loaded transactions for `meru-inc`. Select them from the dropdown on the **Evaluate** page.

### Employees (reference)

| ID | Name | Department | Role | Country |
|----|------|------------|------|---------|
| emp-001 | Alice Chen | Sales | Manager | US |
| emp-002 | Ben Williams | Engineering | IC3 | GB |
| emp-003 | Leila Nasser | Marketing | IC2 | SG |
| emp-004 | Tom Hargreaves | Sales | IC4 | GB |
| emp-005 | Sarah Kim | Engineering | Director | US |

---

### Compliant — Expected verdict: `pass_through`

| Transaction ID | Employee | Amount | Merchant | Why compliant |
|----------------|----------|--------|----------|---------------|
| `a1b2c3d4-0001-0001-0001-000000000001` | emp-001 (Alice) | $220 USD | Marriott Hotels | 4-star hotel under $250 NYC cap, receipt attached |
| `a1b2c3d4-0002-0002-0002-000000000002` | emp-002 (Ben) | $299 USD | Zoom | SaaS under $500/mo threshold, no receipt needed |
| `a1b2c3d4-0004-0004-0004-000000000004` | emp-004 (Tom) | $580 USD | British Airways | Flight with receipt attached |
| `a1b2c3d4-0005-0005-0005-000000000005` | emp-005 (Sarah) | $68 USD | The Capital Grille | Solo lunch under $75 receipt threshold, receipt attached |

---

### Non-Compliant — Expected verdict: `fail` / `block` / `escalate`

| Transaction ID | Employee | Amount | Merchant | Expected action | Reason |
|----------------|----------|--------|----------|-----------------|--------|
| `a1b2c3d4-0006-0006-0006-000000000006` | emp-001 (Alice) | $180 USD | Nobu London | `request_evidence` | Over $75 threshold, no receipt attached |
| `a1b2c3d4-0007-0007-0007-000000000007` | emp-002 (Ben) | $500 USD | Competitor Corp | `block` | Vendor is on blocklist |
| `a1b2c3d4-0009-0009-0009-000000000009` | emp-004 (Tom) | $450 USD | Four Seasons NY | `flag` | 5-star hotel exceeds 4-star limit |
| `a1b2c3d4-0010-0010-0010-000000000010` | emp-005 (Sarah) | $1,200 USD | Salesforce | `escalate` | SaaS above $500/mo, no pre-approval on record |

---

### LLM Judgment Required — Expected verdict: `needs_judgment`

These transactions involve hotels with no official star classification. The rule engine cannot deterministically verify the 4-star limit, so it hands off to the LLM judgment agent.

| Transaction ID | Employee | Amount | Merchant | Why LLM is called |
|----------------|----------|--------|----------|-------------------|
| `a1b2c3d4-0003-0003-0003-000000000003` | emp-003 (Leila) | $42 SGD | citizenM Singapore | Unstarred boutique chain; amount under $75 threshold so no receipt needed |
| `a1b2c3d4-0008-0008-0008-000000000008` | emp-003 (Leila) | $320 USD | The Hoxton London | No official star rating; receipt attached; 2-night stay |
| `a1b2c3d4-0016-0016-0016-000000000016` | emp-005 (Sarah) | €70 EUR | citizenM Amsterdam | Unstarred; receipt attached; €70 ≈ $76 also crosses receipt threshold |

> The LLM will assess based on brand reputation, typical positioning, and policy intent. It returns a verdict, rationale, and confidence score.

---

### Structuring Detection — Consecutive high-value meals just under cap

These three transactions from emp-001 at the same merchant on consecutive nights are each just under the $150 per-meal cap but together total $444. Use these to demonstrate pattern detection or flag for manual review.

| Transaction ID | Date | Amount | Merchant |
|----------------|------|--------|----------|
| `a1b2c3d4-0011-0011-0011-000000000011` | 2026-05-15 | $149 USD | The Capital Grille |
| `a1b2c3d4-0012-0012-0012-000000000012` | 2026-05-16 | $148 USD | The Capital Grille |
| `a1b2c3d4-0013-0013-0013-000000000013` | 2026-05-17 | $147 USD | The Capital Grille |

> Each passes the per-transaction cap individually. Evaluate all three in sequence, then check the dashboard to see the pattern.

---

### Adversarial Scenarios

| Transaction ID | Employee | Amount | Merchant | Scenario |
|----------------|----------|--------|----------|----------|
| `a1b2c3d4-0014-0014-0014-000000000014` | emp-003 (Leila) | $95 USD | The Capital Grille | Receipt attached with alcohol line items ($28 wine), but no attendee note — tests the alcohol NL clause |
| `a1b2c3d4-0015-0015-0015-000000000015` | emp-002 (Ben) | $500 USD | Cmpetitor Corp | Typo of blocked vendor "Competitor Corp" — tests whether fuzzy matching catches it |

---

## Test Data — Custom Upload JSONs

Use these on **Tab B (Upload JSON)** of the Evaluate page.

### 1. LLM judgment — unstarred hotel (The Hoxton)

```json
{
  "transaction_id": "00000000-0000-0000-0000-000000000099",
  "tenant_id": "meru-inc",
  "employee_id": "emp-001",
  "amount": "65.00",
  "currency": "USD",
  "merchant_name": "The Hoxton",
  "mcc_code": "7011",
  "timestamp": "2026-05-18T14:30:00Z",
  "vendor_id": "vnd-017",
  "card_id": "card-sample",
  "description": "1-night hotel stay, London"
}
```

**Expected:** `needs_judgment` — LLM assesses The Hoxton's star equivalence.

---

### 2. Blocklist hit — blocked vendor

```json
{
  "transaction_id": "00000000-0000-0000-0000-000000000100",
  "tenant_id": "meru-inc",
  "employee_id": "emp-002",
  "amount": "750.00",
  "currency": "USD",
  "merchant_name": "Competitor Corp",
  "mcc_code": "7389",
  "timestamp": "2026-05-18T10:00:00Z",
  "vendor_id": "vnd-014",
  "card_id": "card-002",
  "description": "Consulting retainer Q2"
}
```

**Expected:** `fail` with action `block` — vendor_blocklist rule fires.

---

### 3. Receipt required — meal over threshold

```json
{
  "transaction_id": "00000000-0000-0000-0000-000000000101",
  "tenant_id": "meru-inc",
  "employee_id": "emp-004",
  "amount": "120.00",
  "currency": "USD",
  "merchant_name": "Nobu London",
  "mcc_code": "5812",
  "timestamp": "2026-05-18T19:00:00Z",
  "vendor_id": "vnd-013",
  "card_id": "card-004",
  "description": "Team dinner"
}
```

**Expected:** `needs_evidence` with action `request_evidence` — amount > $75, no receipt on file.

---

### 4. SaaS pre-approval required

```json
{
  "transaction_id": "00000000-0000-0000-0000-000000000102",
  "tenant_id": "meru-inc",
  "employee_id": "emp-005",
  "amount": "899.00",
  "currency": "USD",
  "merchant_name": "Salesforce",
  "mcc_code": "7372",
  "timestamp": "2026-05-18T09:00:00Z",
  "vendor_id": "vnd-011",
  "card_id": "card-005",
  "description": "Salesforce Enterprise monthly"
}
```

**Expected:** `fail` with action `escalate` — SaaS > $500/mo, no pre-approval.

---

### 5. Compliant flight

```json
{
  "transaction_id": "00000000-0000-0000-0000-000000000103",
  "tenant_id": "meru-inc",
  "employee_id": "emp-003",
  "amount": "420.00",
  "currency": "USD",
  "merchant_name": "Delta Airlines",
  "mcc_code": "4511",
  "timestamp": "2026-05-18T06:00:00Z",
  "vendor_id": "vnd-007",
  "card_id": "card-003",
  "description": "NYC to SFO economy"
}
```

**Expected:** `pass_through` — airline, no applicable cap rules.

---

### 6. 5-star hotel over limit

```json
{
  "transaction_id": "00000000-0000-0000-0000-000000000104",
  "tenant_id": "meru-inc",
  "employee_id": "emp-001",
  "amount": "520.00",
  "currency": "USD",
  "merchant_name": "Four Seasons New York",
  "mcc_code": "7011",
  "timestamp": "2026-05-18T15:00:00Z",
  "vendor_id": "vnd-004",
  "card_id": "card-001",
  "description": "Conference hotel NYC"
}
```

**Expected:** `fail` with action `flag` — 5-star hotel exceeds the 4-star maximum.

---

## Test Data — Receipt Submission

After evaluating a transaction that returns `needs_evidence`, submit a receipt using the form that appears in the result panel. Use these values:

### Receipt for txn-0006 (Nobu London, $180 dinner)

| Field | Value |
|-------|-------|
| Total amount | `180.00` |
| Currency | `USD` |
| Business purpose | `Client dinner — London partner meeting` |
| Attendees | `Alice Chen, James Park` |

After submitting, the transaction should re-evaluate to `pass_through` (receipt now on file).

---

### Receipt for the uploaded meal JSON (txn-0101)

| Field | Value |
|-------|-------|
| Total amount | `120.00` |
| Currency | `USD` |
| Business purpose | `Team dinner post-sprint` |
| Attendees | `Tom Hargreaves, Leila Nasser, Ben Williams` |

> For uploaded transactions not in stored data, the receipt is saved and the form shows a success message ("Receipt saved"). Re-upload the JSON to re-evaluate with the receipt on file.

---

## Architecture

```
reap-policy-agent/
├── backend/          FastAPI — REST API, rule engine, LLM agents
│   └── app/
│       ├── api.py              All endpoints
│       ├── schemas.py          Pydantic models
│       ├── services/
│       │   ├── orchestrator.py Evaluation pipeline
│       │   └── policy_store.py Policy lifecycle management
│       └── agents/
│           ├── policy_compiler.py  LLM → structured rules
│           └── judgment_agent.py   LLM verdict for ambiguous cases
├── frontend/         Next.js 14 + Tailwind CSS + shadcn/ui
│   └── app/
│       ├── page.tsx            Dashboard
│       ├── evaluate/           Evaluate page (stored + upload tabs)
│       └── policy/create/      Policy create + review
└── mcp_server/       MCP tools + mock data
    └── data/
        ├── transactions.json   16 pre-loaded transactions
        ├── employees.json      5 employees
        ├── vendors.json        18 vendors (2 blocklisted, 2 unstarred)
        ├── receipts.json       7 pre-loaded receipts
        └── policies/meru-inc/  Compiled policy JSON files
```

### Evaluation Pipeline

```
Transaction
    │
    ▼
Rule Engine ──── all rules pass ──────────────────────► pass_through
    │
    ├── receipt missing ───────────────────────────────► needs_evidence
    │                                                        │
    │                                                   Submit Receipt
    │                                                        │
    │                                                   Re-evaluate ──► pass_through
    │
    ├── rule hard-fails (blocklist, SaaS cap, etc.) ───► fail / escalate / block
    │
    └── hotel star rating unknown ──► LLM Judgment Agent ──► verdict + rationale
```

### Policy Lifecycle

```
Plain text  ──►  LLM Policy Compiler  ──►  draft
                                              │
                                        Human review
                                         ├── Approve ──► active  (previous version deprecated)
                                         └── Reject  ──► back to create
```

### When the LLM is Called

| Trigger | Example transactions |
|---------|---------------------|
| Hotel has no official star classification | txn-0003, txn-0008, txn-0016 |
| Alcohol clause — clients present check | txn-0014 |
| Uploaded transaction with unstarred hotel | sample JSON (vnd-017 / vnd-018) |

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/evaluate` | Evaluate a stored transaction by ID |
| `POST` | `/evaluate/upload` | Evaluate a transaction from uploaded JSON |
| `GET` | `/transactions` | List all stored transactions |
| `GET` | `/employees` | List all employees |
| `GET` | `/vendors` | List all vendors |
| `GET` | `/receipts` | List all receipts |
| `GET` | `/decisions` | List recent decisions from audit log |
| `GET` | `/decisions/{transaction_id}` | Full audit trail for one transaction |
| `GET` | `/policy/active?tenant_id=` | Get active policy for a tenant |
| `GET` | `/policies/{policy_id}` | Get any policy by ID |
| `POST` | `/policies/compile` | Compile policy text → draft |
| `POST` | `/policies/upload` | Upload `.txt` file → draft |
| `POST` | `/policies/{policy_id}/approve` | Promote draft → active |
| `POST` | `/receipts` | Submit a receipt and persist to disk |

Interactive API explorer: `http://localhost:8000/docs`

---

## Environment Variables

Create `reap-policy-agent/frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_TENANT_ID=meru-inc
```

These are set to the correct defaults — no changes needed for local development.
