"""
Policy versioning service.

Storage layout:
    mcp_server/data/policies/{tenant_id}/{policy_id}.compiled.json

Each file holds one CompiledPolicy JSON blob. Version numbers are assigned
per-tenant (monotonically increasing); the file name is keyed by policy_id.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.schemas import CompiledPolicy, PolicyStatus

_POLICY_DIR = Path(__file__).resolve().parents[3] / "mcp_server" / "data" / "policies"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _tenant_dir(tenant_id: str) -> Path:
    return _POLICY_DIR / tenant_id


def _policy_path(tenant_id: str, policy_id: str) -> Path:
    return _tenant_dir(tenant_id) / f"{policy_id}.compiled.json"


def _write(policy: CompiledPolicy) -> None:
    path = _policy_path(policy.tenant_id, str(policy.policy_id))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(policy.model_dump_json(indent=2))


def _load_all(tenant_id: str) -> list[CompiledPolicy]:
    """All compiled policies for a tenant, sorted by version ascending."""
    d = _tenant_dir(tenant_id)
    if not d.exists():
        return []
    policies: list[CompiledPolicy] = []
    for path in d.glob("*.compiled.json"):
        try:
            policies.append(CompiledPolicy.model_validate_json(path.read_text()))
        except Exception:
            pass  # skip corrupt files
    return sorted(policies, key=lambda p: p.version)


def _find_by_id(policy_id: str) -> CompiledPolicy | None:
    """Locate a policy by ID without knowing its tenant (searches all tenant dirs)."""
    for path in _POLICY_DIR.glob(f"*/{policy_id}.compiled.json"):
        try:
            return CompiledPolicy.model_validate_json(path.read_text())
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_draft(compiled_policy: CompiledPolicy) -> str:
    """Persist a compiled policy as a draft.

    Auto-assigns the next version number for the tenant (max existing + 1).
    Always forces status to draft regardless of what the caller set.

    Returns the policy_id as a string.
    """
    existing = _load_all(compiled_policy.tenant_id)
    next_version = max((p.version for p in existing), default=0) + 1

    policy = compiled_policy.model_copy(update={
        "status": PolicyStatus.draft,
        "version": next_version,
        "approved_by": None,
        "approved_at": None,
    })
    _write(policy)
    return str(policy.policy_id)


def approve(policy_id: str, reviewer_id: str) -> CompiledPolicy:
    """Promote a draft policy to active and deprecate the previous active version.

    Lifecycle: draft → approved → active (both transitions happen in one call).

    Raises:
        FileNotFoundError: policy_id does not exist on disk.
        ValueError: policy is not in draft or approved status.
    """
    policy = _find_by_id(policy_id)
    if policy is None:
        raise FileNotFoundError(f"Policy {policy_id!r} not found.")

    if policy.status not in (PolicyStatus.draft, PolicyStatus.approved):
        raise ValueError(
            f"Cannot approve policy {policy_id!r}: "
            f"current status is '{policy.status.value}' (expected 'draft' or 'approved')."
        )

    now = datetime.now(timezone.utc)

    # Deprecate any currently active version for this tenant
    for existing in _load_all(policy.tenant_id):
        if existing.status == PolicyStatus.active:
            _write(existing.model_copy(update={"status": PolicyStatus.deprecated}))

    # draft → approved → active in one step
    active = policy.model_copy(update={
        "status": PolicyStatus.active,
        "approved_by": reviewer_id,
        "approved_at": now,
    })
    _write(active)
    return active


def get_active(tenant_id: str) -> CompiledPolicy | None:
    """Return the currently active policy for a tenant, or None."""
    for policy in _load_all(tenant_id):
        if policy.status == PolicyStatus.active:
            return policy
    return None


def get_version(tenant_id: str, version: int) -> CompiledPolicy | None:
    """Return a specific version of a tenant's policy, or None if not found."""
    for policy in _load_all(tenant_id):
        if policy.version == version:
            return policy
    return None


def list_versions(tenant_id: str) -> list[CompiledPolicy]:
    """Return all policy versions for a tenant, sorted by version ascending."""
    return _load_all(tenant_id)
