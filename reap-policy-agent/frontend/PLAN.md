# Frontend Plan: Next.js + Tailwind UI for Policy Enforcement Agent

---

## Project Location
`reap-policy-agent/frontend/` (alongside `backend/` and `mcp_server/`)

---

## Tech Stack
- **Next.js 14** (App Router)
- **Tailwind CSS**
- **shadcn/ui** (Button, Badge, Table, Card, Dialog, Tabs, Textarea, Select)
- **TypeScript**

---

## UI Theme and CSS Direction

- Use the Reap website colour pattern as the visual base.
- Primary brand background should use Reap teal:

```css
background-color: var(--brand-color--teal);
color: #ecf0ef;
```

- Use `#ecf0ef` for text/icons on teal surfaces.
- Use white and black as the main neutral colours for cards, panels, page backgrounds, borders, and body text.
- Keep the UI clean and operational: compact tables, clear status badges, restrained cards, and no decorative gradients.
- Tailwind theme should expose semantic tokens such as `brand-teal`, `brand-light`, `surface`, `ink`, and `border`.

---

## Core User Flow (Step-by-Step)

The UI is a guided 3-step workflow, not a tabbed dashboard.

```
Step 1: Create Policy
  → Paste policy text into a textarea  OR  upload a .txt file
  → POST /policies/upload
  → Show compiled output: structured rules + NL references + unsupported clauses

Step 2: Approve or Reject Policy
  → Reviewer sees the compiled policy
  → Click Approve  → POST /policies/{id}/approve  → policy becomes active
  → Click Reject   → policy is discarded, user goes back to Step 1

Step 3: Evaluate a Transaction
  Two options on the same page (tabs):

  Option A — Stored Data
  → Dropdown of all transactions from GET /transactions (enriched with employee name + receipt indicator)
  → On select: preview card shows transaction details, employee, vendor, receipt status
  → Click Evaluate → POST /evaluate {transaction_id}

  Option B — Upload JSON
  → Upload a .json file matching the Transaction schema
  → Preview card shows parsed data before evaluating
  → Click Evaluate → POST /evaluate/upload (multipart file)
  → Sample JSON download link shows expected format

  Both options show the same Decision result panel below:
  → Verdict badge, action badge, confidence bar, rules fired, LLM rationale if used
  → "Evaluate another" resets the tab
```

---

## Pages

| Route | Purpose |
|-------|---------|
| `/` | Dashboard — recent decisions + summary metrics |
| `/policy/create` | Step 1: Policy input (textarea + file upload) |
| `/policy/review/[id]` | Step 2: Review compiled policy, Approve or Reject |
| `/evaluate` | Step 3: Select transaction from stored list + run evaluation |
| `/evaluate/[decisionId]` | Decision result detail + audit trail |

---

## Directory Structure

```
frontend/
├── app/
│   ├── layout.tsx
│   ├── page.tsx                         # Dashboard
│   ├── policy/
│   │   ├── create/
│   │   │   └── page.tsx                 # Step 1: policy input
│   │   └── review/
│   │       └── [id]/
│   │           └── page.tsx             # Step 2: approve / reject
│   └── evaluate/
│       ├── page.tsx                     # Step 3: transaction selector + evaluate
│       └── [decisionId]/
│           └── page.tsx                 # Decision detail + audit trail
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx
│   │   └── TopBar.tsx
│   ├── ui/
│   │   ├── VerdictBadge.tsx
│   │   ├── ActionBadge.tsx
│   │   └── ConfidenceBar.tsx
│   ├── policy/
│   │   ├── PolicyInputForm.tsx          # Textarea + file upload toggle
│   │   ├── CompiledPolicyPreview.tsx    # Shows rules + NL refs after compile
│   │   ├── PolicyApproveReject.tsx      # Approve / Reject buttons + confirmation
│   │   └── PolicyRulesTable.tsx
│   └── evaluate/
│       ├── StoredTransactionTab.tsx     # Dropdown + enriched preview card
│       ├── UploadTransactionTab.tsx     # JSON file upload + preview card
│       ├── TransactionPreviewCard.tsx   # Shared preview layout (used by both tabs)
│       ├── DecisionPanel.tsx            # Verdict + action + confidence + rules
│       └── AuditTrail.tsx
├── lib/
│   ├── api.ts                           # All API calls
│   └── types.ts                         # TypeScript types
├── public/
│   └── sample-transaction.json          # Sample transaction file served for download
└── .env.local
```

---

## Page Details

### `/policy/create` — Step 1
- Toggle between **Paste text** (textarea) and **Upload file** (.txt)
- `tenant_id` pre-filled from env (`meru-inc`)
- Submit → POST /policies/upload → redirect to `/policy/review/[policy_id]`
- Show loading state while compiling

### `/policy/review/[id]` — Step 2
- Header: policy version, status badge (`draft`)
- **Structured Rules** table: predicate, parameters, action on violation, source clause
- **Natural Language References** list: clause text + keywords
- **Unsupported Clauses** list (if any): clause + reason compiler skipped it
- Two buttons at the bottom:
  - **Approve** → POST /policies/{id}/approve → status becomes `active` → redirect to `/evaluate`
  - **Reject** → discard, redirect back to `/policy/create`

### `/evaluate` — Step 3
Two tabs on the same page:

**Tab A — Stored Data**
- On page load: fetch `GET /transactions`, `GET /employees`, `GET /receipts` in parallel
- Build a lookup map: `employee_id → { name, department, role_level, country }` so raw IDs like `emp-002` are never shown to the user
- Dropdown option format: `merchant_name — $amount currency — Employee Name (Department)`
  - Example: `Zoom — $299 USD — Ben Williams (Engineering)`
  - Example: `Grab — SGD 42 — Leila Nasser (Marketing)`
- On selection: preview card shows:
  - Amount + currency
  - Merchant name + MCC code
  - Employee: full name, department, role level, country (never the raw ID)
  - Receipt attached: Yes / No (checked against receipts list by transaction_id)
  - Vendor: name + blocklist badge if `on_blocklist: true`
- **Evaluate** button → `POST /evaluate {transaction_id}` → Decision panel below

**Tab B — Upload JSON**
- Drag-and-drop or browse file picker (`.json` only)
- After file selected: preview card shows parsed fields (same layout as Tab A)
- Sample JSON download link (pre-filled with a valid Transaction example)
- **Evaluate** button → `POST /evaluate/upload` → Decision panel below

**Shared Decision Panel** (shown after either path):
- VerdictBadge + ActionBadge
- Confidence bar (0–100%)
- Rules fired list (rule_id + predicate + source clause)
- LLM indicator badge + rationale block if `agent_used: true`
- "Evaluate another" resets to the tab without clearing the selection

### `/` — Dashboard
- 4 stat cards: Total Evaluated / Passed / Failed / Needs Review (from GET /decisions)
- Recent decisions table: merchant, amount, verdict badge, action, timestamp, link to detail
- "Create Policy" and "Evaluate Transaction" shortcut buttons

### `/evaluate/[decisionId]` — Decision Detail
- Full decision breakdown
- Audit trail timeline (GET /decisions/{transaction_id})

---

## API Integration

| Function | Endpoint | Input |
|----------|---------|-------|
| `uploadPolicy(tenantId, file)` | `POST /policies/upload` | multipart form (file + tenant_id) → returns `CompiledPolicy` |
| `compilePolicyText(tenantId, text)` | `POST /policies/compile` | JSON body `{tenant_id, policy_text}` → returns `CompiledPolicy` |
| `approvePolicy(policyId, reviewerId?)` | `POST /policies/{id}/approve` | JSON body `{reviewer_id}` → returns `CompiledPolicy` |
| `getActivePolicy(tenantId)` | `GET /policy/active` | query param `tenant_id` |
| `evaluate(transactionId)` | `POST /evaluate` | JSON body `{transaction_id}` → returns `Decision` |
| `evaluateUpload(file)` | `POST /evaluate/upload` | multipart file (.json) → returns `Decision` |
| `listTransactions()` | `GET /transactions` | returns all stored `Transaction[]` |
| `listEmployees()` | `GET /employees` | returns all stored `Employee[]` |
| `listVendors()` | `GET /vendors` | returns all stored `Vendor[]` |
| `listReceipts()` | `GET /receipts` | returns all stored `Receipt[]` |
| `listDecisions(limit?)` | `GET /decisions` | query param `limit` |
| `getDecisions(transactionId)` | `GET /decisions/{id}` | path param |

---

## Verdict Colour Map

| Verdict | Colour |
|---------|--------|
| `pass_through` | Green |
| `needs_evidence` | Yellow |
| `needs_judgment` | Orange |
| `fail` | Red |
| `abstain` | Gray |

---

## Environment

```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_TENANT_ID=meru-inc
```

---

## Implementation Order

1. Next.js + Tailwind + shadcn/ui scaffold
2. `lib/types.ts`, `lib/api.ts`, `public/sample-transaction.json`
3. Layout: Sidebar, TopBar, root layout
4. UI atoms: VerdictBadge, ActionBadge, ConfidenceBar
5. `/policy/create` — PolicyInputForm
6. `/policy/review/[id]` — CompiledPolicyPreview + PolicyApproveReject
7. `/evaluate` — TransactionSelector + DecisionPanel
8. `/` Dashboard
9. `/evaluate/[decisionId]` — Decision detail + AuditTrail

---

## Verification

1. Start backend: `uvicorn backend.app.api:app --reload` from `reap-policy-agent/`
2. Start frontend: `npm run dev` from `reap-policy-agent/frontend/`

**Policy flow**
3. Open `http://localhost:3000/policy/create`
4. Paste policy text OR upload a `.txt` file → submit → compiled rules appear on review page
5. Confirm structured rules table and NL references are visible
6. Click Approve → status becomes `active` → redirected to `/evaluate`
7. Click Reject → redirected back to `/policy/create`

**Evaluate — Stored Data tab**
8. Dropdown loads with all 16 transactions — verify labels show full employee names (e.g. "Ben Williams", not "emp-002")
9. Select `Competitor Corp — $500 USD — Ben Williams (Engineering)` → preview card shows blocklist badge on vendor → click Evaluate → red `fail` badge
10. Select `Zoom — $299 USD — Ben Williams (Engineering)` → preview card shows no receipt attached → click Evaluate → yellow `needs_evidence` badge
11. Select `Grab — SGD 42 — Leila Nasser (Marketing)` → Evaluate → green `pass_through` badge

**Evaluate — Upload JSON tab**
12. Click "Download sample JSON" → edit `merchant_name` to `"Competitor Corp"` → upload → preview card appears → Evaluate → red `fail` badge
13. Upload a JSON with `amount: 180, currency: "USD", merchant_name: "Nobu London"` and no receipt → Evaluate → yellow `needs_evidence` badge

**Dashboard**
14. Open `http://localhost:3000` → stat cards show updated counts after each evaluation
15. Recent decisions table shows merchant, amount, verdict badge, and timestamp for all evaluated transactions
