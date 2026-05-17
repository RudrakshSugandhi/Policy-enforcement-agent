from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

app = FastAPI(title="Reap Policy Agent")

# root of mcp_server/data/policies/ relative to this file
_POLICY_DIR = (
    Path(__file__).resolve().parent.parent.parent / "mcp_server" / "data" / "policies"
)


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

class PolicyUploadResponse(BaseModel):
    policy_id: str
    filename: str
    status: str = "uploaded"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/policies/upload", response_model=PolicyUploadResponse)
async def upload_policy(
    tenant_id: str = Form(...),
    file: UploadFile = File(...),
) -> PolicyUploadResponse:
    """Upload a .txt policy file for a tenant.

    Form fields:
      - tenant_id: the company this policy belongs to
      - file: the .txt policy document

    No LLM involvement yet — pure persistence. Compilation happens in Phase 5.2.
    """
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

    return PolicyUploadResponse(
        policy_id=policy_id,
        filename=file.filename,
    )
