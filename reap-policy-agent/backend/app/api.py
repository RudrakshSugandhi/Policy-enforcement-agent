import json
import sys
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.schemas import CompiledPolicy, Decision
from app.services import policy_store

# Make mcp_server importable (sibling package)
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

app = FastAPI(title="Reap Policy Agent")

_POLICY_DIR = _ROOT / "mcp_server" / "data" / "policies"
_AUDIT_LOG = _ROOT / "mcp_server" / "data" / "audit_log.jsonl"


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class EvaluateRequest(BaseModel):
    transaction_id: str


class PolicyUploadResponse(BaseModel):
    policy_id: str
    filename: str
    status: str = "uploaded"


class ApproveRequest(BaseModel):
    reviewer_id: str = "api-user"


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
    """Evaluate a single transaction end-to-end and return a Decision."""
    from app.services.orchestrator import evaluate as _evaluate
    try:
        return _evaluate(body.transaction_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


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


@app.post("/policies/upload", response_model=PolicyUploadResponse)
async def upload_policy(
    tenant_id: str = Form(...),
    file: UploadFile = File(...),
) -> PolicyUploadResponse:
    """Upload a .txt policy file for a tenant (stored as a raw draft)."""
    if not tenant_id.strip():
        raise HTTPException(status_code=422, detail="tenant_id must not be empty")
    if not file.filename or not file.filename.endswith(".txt"):
        raise HTTPException(status_code=422, detail="Only .txt files are accepted")

    content = await file.read()
    policy_text = content.decode("utf-8").strip()
    if not policy_text:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")

    policy_id = str(uuid4())
    tenant_dir = _POLICY_DIR / tenant_id.strip()
    tenant_dir.mkdir(parents=True, exist_ok=True)
    (tenant_dir / f"{policy_id}.txt").write_text(policy_text)

    return PolicyUploadResponse(policy_id=policy_id, filename=file.filename)


@app.post("/policies/{policy_id}/approve", response_model=CompiledPolicy)
def approve_policy(policy_id: str, body: ApproveRequest = ApproveRequest()) -> CompiledPolicy:
    """Approve a draft policy and make it the active version for its tenant."""
    try:
        return policy_store.approve(policy_id, body.reviewer_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
