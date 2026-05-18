# Reap Policy Enforcement Agent

An AI-powered expense policy enforcement system. Upload a plain-text policy, compile it into structured rules via LLM, then evaluate transactions against it — deterministically or via LLM judgment.

---

## Quick Start

### Prerequisites

| Tool | Version |
|------|---------|
| Python | ≥ 3.11 |
| Conda | any |
| Node.js | ≥ 18 |
| Ollama | latest |

---

### 1 — Pull the model

```bash
ollama pull qwen2.5:7b-instruct
```

---

### 2 — Backend

```bash
# From reap-policy-agent/
conda activate reap-policy-agent
pip install -e backend/
uvicorn backend.app.api:app --reload --port 8000
```

Backend runs at `http://localhost:8000`

---

### 3 — Frontend

```bash
# From reap-policy-agent/frontend/
npm install
npm run dev
```

Frontend runs at `http://localhost:3000`

---

## Complete Workflow

The application has three stages that connect in sequence.

---

### Stage 1 — Create & Approve a Policy

**Go to:** `localhost:3000/policy/create`

1. Paste your expense policy text into the editor, or upload a `.txt` file.
2. Click **Compile policy** — the LLM reads the text and extracts:
   - **Structured rules** — measurable checks (amount caps, vendor blocklists, star limits)
   - **Natural language references** — clauses that require human judgment (e.g. "clients must be present")
   - **Unsupported clauses** — governance obligations the agent cannot enforce at transaction level
3. You are redirected to the **Review** page showing the compiled output.
4. Click **Approve policy** — the policy becomes active and all future evaluations run against it.
5. Click **Reject** — returns to the create page to revise the text.

> Only one policy can be active per tenant at a time. Approving a new one automatically deprecates the previous version.

<!-- screenshot: create / review policy page -->

&nbsp;

---

### Stage 2 — Evaluate Transactions

**Go to:** `localhost:3000/evaluate`

Two tabs are available:

**Tab A — Stored data**

1. Select a transaction from the dropdown. Employee name, department, amount, and merchant are shown in the preview card.
2. Click **Evaluate** — the backend runs the rule engine against the active policy.
3. The result panel shows:
   - **Verdict badge** — pass, fail, needs evidence, needs judgment, or abstain
   - **Action taken** — block, flag, request evidence, escalate, etc.
   - **Rules violated** — each fired rule shown as a named card with the source policy clause
   - **LLM judgment badge** — shown when the judgment agent was invoked
   - **LLM rationale** — natural-language explanation when the agent was used
   - **Confidence** — 0.0 (uncertain) to 1.0 (fully deterministic)

**Tab B — Upload JSON**

1. Drag and drop or select a `.json` file matching the transaction schema.
2. A preview of the parsed transaction is shown before submission.
3. Click **Evaluate** — same result panel as Tab A.
4. Download `sample-transaction.json` for a pre-built example that triggers LLM judgment.

**Receipt submission**

When the verdict is `needs_evidence` (receipt required), a **Submit Receipt** form appears below the result:

1. Enter the receipt total, currency, business purpose, and optional attendees.
2. Click **Submit receipt & re-evaluate** — the receipt is saved and the transaction is re-evaluated immediately.
3. The verdict updates in place (typically to `pass_through` once the receipt is on file).

<!-- screenshot: evaluate page -->

&nbsp;

---

### Stage 3 — Review on the Dashboard

**Go to:** `localhost:3000`

- **Stat cards** show total evaluated, passed, failed, and needs-review counts.
- **Recent decisions table** lists the latest 10 evaluations with verdict, action, and an **LLM judgment** badge for any row where the agent was invoked.
- Click **View** on any row to open the full decision detail and audit trail.
- Click **Refresh** to reload the feed after new evaluations.

<!-- screenshot: dashboard -->

&nbsp;

---

## When the LLM is Called

The judgment agent fires when the rule engine cannot produce a deterministic verdict:

| Trigger | Example |
|---------|---------|
| Hotel with no official star classification | citizenM, The Hoxton |
| Clause requiring human context | "Alcohol reimbursable only when clients are present" |

Three stored transactions are pre-configured to trigger the LLM:

| Transaction | Merchant | Amount | Why |
|-------------|----------|--------|-----|
| txn-0003 | citizenM Singapore | $42 SGD | Unstarred hotel, amount under receipt threshold |
| txn-0008 | The Hoxton London | $320 USD | Unstarred hotel, receipt attached |
| txn-0016 | citizenM Amsterdam | €70 EUR | Unstarred hotel, borderline currency conversion |

To trigger it from an uploaded file, use the sample JSON (available via the Download button on the Upload tab):

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

---

## Architecture

```
reap-policy-agent/
├── backend/          FastAPI — REST API, rule engine, LLM agents
├── frontend/         Next.js 14 — reviewer UI
└── mcp_server/       MCP tools + mock data (transactions, employees, vendors)
```

**Evaluation pipeline**

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

**Policy lifecycle**

```
Plain text  ──►  LLM Policy Compiler  ──►  draft
                                              │
                                        Human review
                                         ├── Approve ──► active  (previous version deprecated)
                                         └── Reject  ──► back to create
```

---

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/policies/compile` | Compile policy text → draft |
| `POST` | `/policies/upload` | Upload `.txt` file → draft |
| `GET` | `/policies/{id}` | Fetch policy by ID |
| `POST` | `/policies/{id}/approve` | Promote draft → active |
| `GET` | `/policy/active` | Get current active policy |
| `POST` | `/evaluate` | Evaluate stored transaction by ID |
| `POST` | `/evaluate/upload` | Evaluate uploaded JSON transaction |
| `POST` | `/receipts` | Submit a receipt and update stored data |
| `GET` | `/decisions` | List recent decisions (audit log) |
| `GET` | `/decisions/{transaction_id}` | Full audit trail for one transaction |

---

## Environment Variables

```env
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_TENANT_ID=meru-inc
```
