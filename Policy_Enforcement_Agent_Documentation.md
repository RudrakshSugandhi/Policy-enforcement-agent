# Policy Enforcement Agent — Design Doc

## Three Important Evaluation Areas

1. **Product thinking**: what problem we solve, for whom, and what actions the agent should take.
2. **Architecture and technology choices**: how policies, rules, LLMs, receipts, and actions work together.
3. **Production-ready solution**: how the system handles safety, auditability, versioning, scale, and human review.

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
- **LLM**: prefer open-source LLMs instead of external closed models.
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

## 11. Minimal Demo Output

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

## 12. Final Position

- Build the agent workflow first.
- Use hybrid policy representation.
- Run structured rules before LLM.
- Prefer open-source LLMs for ambiguous cases.
- Use post-authorization real-time checks as the main decision point.
- Keep high-stakes actions under human approval.
- Make every decision explainable, versioned, and auditable.

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
