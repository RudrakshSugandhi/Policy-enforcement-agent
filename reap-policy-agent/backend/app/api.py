import json
import sys
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agents.policy_compiler import compile_policy as _compile_policy
from app.schemas import CompiledPolicy, Decision, Employee, Receipt, Transaction, Vendor
from app.services import policy_store

# Make mcp_server importable (sibling package)
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

app = FastAPI(title="Reap Policy Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_AUDIT_LOG = _ROOT / "mcp_server" / "data" / "audit_log.jsonl"


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class EvaluateRequest(BaseModel):
    transaction_id: str


class CompileRequest(BaseModel):
    tenant_id: str
    policy_text: str


class ApproveRequest(BaseModel):
    reviewer_id: str = "api-user"


class ReceiptSubmitRequest(BaseModel):
    transaction_id: str
    total_amount: str
    currency: str = "USD"
    business_purpose: str | None = None
    attendees: list[str] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_audit_log() -> list[dict]:
    if not _AUDIT_LOG.exists():
        return []
    return [
        json.loads(line)
        for line in _AUDIT_LOG.read_text().splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/evaluate", response_model=Decision)
def evaluate(body: EvaluateRequest) -> Decision:
    """Evaluate a stored transaction by ID and return a Decision."""
    from app.services.orchestrator import evaluate as _evaluate
    try:
        return _evaluate(body.transaction_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/evaluate/upload", response_model=Decision)
async def evaluate_upload(file: UploadFile = File(...)) -> Decision:
    """Evaluate a transaction supplied as a JSON file upload.

    The file must be a valid JSON object matching the Transaction schema.
    Employee, vendor, and receipt context are looked up from stored data
    using the IDs present in the uploaded transaction.
    """
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=422, detail="Only .json files are accepted")

    content = await file.read()
    try:
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid JSON: {exc}")

    try:
        txn = Transaction.model_validate(data)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid transaction data: {exc}")

    from app.services.orchestrator import evaluate_direct
    return evaluate_direct(txn)


@app.get("/transactions", response_model=list[Transaction])
def list_transactions() -> list[Transaction]:
    """Return all stored transactions."""
    from mcp_server.tools.read_tools import _transactions
    results = []
    for row in _transactions:
        try:
            results.append(Transaction.model_validate(row))
        except Exception:
            pass
    return results


@app.get("/employees", response_model=list[Employee])
def list_employees() -> list[Employee]:
    """Return all stored employees."""
    from mcp_server.tools.read_tools import _employees
    results = []
    for row in _employees:
        try:
            results.append(Employee.model_validate(row))
        except Exception:
            pass
    return results


@app.get("/vendors", response_model=list[Vendor])
def list_vendors() -> list[Vendor]:
    """Return all stored vendors."""
    from mcp_server.tools.read_tools import _vendors
    results = []
    for row in _vendors:
        try:
            results.append(Vendor.model_validate(row))
        except Exception:
            pass
    return results


@app.get("/receipts", response_model=list[Receipt])
def list_receipts() -> list[Receipt]:
    """Return all stored receipts."""
    from mcp_server.tools.read_tools import _receipts
    results = []
    for row in _receipts:
        try:
            results.append(Receipt.model_validate(row))
        except Exception:
            pass
    return results


@app.get("/decisions", response_model=list[Decision])
def list_decisions(limit: int = 50) -> list[Decision]:
    """Return the most recent decisions from the audit log (newest first)."""
    rows = _read_audit_log()
    decisions = []
    for row in reversed(rows[-limit:]):
        try:
            decisions.append(Decision.model_validate(row))
        except Exception:
            pass
    return decisions


@app.get("/decisions/{transaction_id}", response_model=list[Decision])
def get_decisions(transaction_id: str) -> list[Decision]:
    """Return the full audit trail for a specific transaction (oldest first)."""
    rows = _read_audit_log()
    decisions = []
    for row in rows:
        if str(row.get("transaction_id")) == transaction_id:
            try:
                decisions.append(Decision.model_validate(row))
            except Exception:
                pass
    if not decisions:
        raise HTTPException(status_code=404, detail="No decisions found for this transaction.")
    return decisions


@app.get("/policy/active", response_model=CompiledPolicy)
def get_active_policy(tenant_id: str) -> CompiledPolicy:
    """Return the currently active compiled policy for a tenant."""
    policy = policy_store.get_active(tenant_id)
    if policy is None:
        raise HTTPException(status_code=404, detail=f"No active policy for tenant '{tenant_id}'.")
    return policy


@app.post("/policies/upload", response_model=CompiledPolicy)
async def upload_policy(
    tenant_id: str = Form(...),
    file: UploadFile = File(...),
) -> CompiledPolicy:
    """Upload a .txt policy file, compile it via LLM, and save as a draft CompiledPolicy."""
    if not tenant_id.strip():
        raise HTTPException(status_code=422, detail="tenant_id must not be empty")
    if not file.filename or not file.filename.endswith(".txt"):
        raise HTTPException(status_code=422, detail="Only .txt files are accepted")

    content = await file.read()
    policy_text = content.decode("utf-8").strip()
    if not policy_text:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")

    policy_id = str(uuid4())
    try:
        compiled = await _compile_policy(tenant_id.strip(), policy_id, policy_text)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return policy_store.save_draft(compiled)


@app.post("/policies/compile", response_model=CompiledPolicy)
async def compile_policy_text(body: CompileRequest) -> CompiledPolicy:
    """Compile raw policy text (e.g. from a textarea) and save as a draft CompiledPolicy."""
    if not body.tenant_id.strip():
        raise HTTPException(status_code=422, detail="tenant_id must not be empty")
    if not body.policy_text.strip():
        raise HTTPException(status_code=422, detail="policy_text must not be empty")

    policy_id = str(uuid4())
    try:
        compiled = await _compile_policy(body.tenant_id.strip(), policy_id, body.policy_text.strip())
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return policy_store.save_draft(compiled)


@app.get("/policies/{policy_id}", response_model=CompiledPolicy)
def get_policy(policy_id: str) -> CompiledPolicy:
    """Return a policy by ID regardless of status."""
    policy = policy_store.get_by_id(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found.")
    return policy


@app.post("/policies/{policy_id}/approve", response_model=CompiledPolicy)
def approve_policy(policy_id: str, body: ApproveRequest = ApproveRequest()) -> CompiledPolicy:
    """Approve a draft policy and make it the active version for its tenant."""
    try:
        return policy_store.approve(policy_id, body.reviewer_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.post("/receipts", response_model=Receipt)
def submit_receipt(body: ReceiptSubmitRequest) -> Receipt:
    """Submit a receipt for a transaction. Persists to disk and updates in-memory store."""
    from mcp_server.tools import read_tools as _rt

    receipt = Receipt(
        receipt_id=uuid4(),
        transaction_id=body.transaction_id,
        total_amount=body.total_amount,
        currency=body.currency,
        line_items=[],
        business_purpose=body.business_purpose,
        attendees=[a.strip() for a in body.attendees if a.strip()] if body.attendees else None,
    )
    receipt_dict = json.loads(receipt.model_dump_json())

    replaced = False
    for i, r in enumerate(_rt._receipts):
        if str(r.get("transaction_id")) == str(body.transaction_id):
            _rt._receipts[i] = receipt_dict
            replaced = True
            break
    if not replaced:
        _rt._receipts.append(receipt_dict)

    receipts_path = _ROOT / "mcp_server" / "data" / "receipts.json"
    receipts_path.write_text(json.dumps(_rt._receipts, indent=2, default=str))

    return receipt
