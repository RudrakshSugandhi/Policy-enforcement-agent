"""Write tools — each tool mutates state and/or sends notifications.

All file I/O is append-only to JSONL files in mcp_server/data/.
Functions are defined at module level so the action dispatcher can call them
directly without going through MCP.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DATA = Path(__file__).resolve().parent.parent / "data"

_NOTIFICATIONS = DATA / "notifications.jsonl"
_REVIEW_QUEUE  = DATA / "review_queue.jsonl"
_COMPLIANT_LOG = DATA / "compliant_log.jsonl"
_HUMAN_QUEUE   = DATA / "human_approval_queue.jsonl"


def _append(path: Path, record: dict) -> None:
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")


def _queue_length(path: Path) -> int:
    try:
        lines = [l for l in path.read_text().splitlines() if l.strip()]
        return len(lines)
    except FileNotFoundError:
        return 0


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def request_evidence(
    transaction_id: str,
    items: list[str],
    deadline_hours: int = 48,
) -> dict:
    """Ask the employee to upload missing evidence (receipt, manager approval, etc.).

    Prints the intended notification and writes to notifications.jsonl.
    Returns {status, request_id, message}.
    """
    request_id = str(uuid.uuid4())
    record = {
        "type": "evidence_request",
        "request_id": request_id,
        "transaction_id": transaction_id,
        "items": items,
        "deadline_hours": deadline_hours,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _append(_NOTIFICATIONS, record)
    print(
        f"[NOTIFY] Transaction {transaction_id}: please upload "
        f"{', '.join(items)} within {deadline_hours}h (request {request_id})."
    )
    return {
        "status": "sent",
        "request_id": request_id,
        "message": (
            f"Evidence request sent for: {', '.join(items)}. "
            f"Deadline: {deadline_hours}h."
        ),
    }


def flag_for_review(
    transaction_id: str,
    reason: str,
    severity: str = "medium",
) -> dict:
    """Add the transaction to the finance review queue.

    Appends to review_queue.jsonl. Returns {status, queue_position}.
    severity: "low" | "medium" | "high"
    """
    record = {
        "type": "review_flag",
        "transaction_id": transaction_id,
        "reason": reason,
        "severity": severity,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _append(_REVIEW_QUEUE, record)
    position = _queue_length(_REVIEW_QUEUE)
    return {"status": "queued", "queue_position": position}


def mark_compliant(transaction_id: str, policy_version: int) -> dict:
    """Record that the transaction passed all policy checks.

    Appends to compliant_log.jsonl. Returns {status}.
    """
    record = {
        "type": "compliant",
        "transaction_id": transaction_id,
        "policy_version": policy_version,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _append(_COMPLIANT_LOG, record)
    return {"status": "compliant"}


def notify_manager(
    transaction_id: str,
    manager_id: str,
    reason: str,
) -> dict:
    """Send an escalation notification to the employee's manager.

    Prints the intended message (mock — production replaces this with Slack/email).
    Returns {status}.
    """
    record = {
        "type": "manager_notification",
        "transaction_id": transaction_id,
        "manager_id": manager_id,
        "reason": reason,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _append(_NOTIFICATIONS, record)
    print(
        f"[NOTIFY MANAGER] {manager_id} — "
        f"transaction {transaction_id} requires your attention: {reason}"
    )
    return {"status": "notified"}


def propose_high_stakes_action(
    transaction_id: str,
    action: str,
    justification: str,
) -> dict:
    """Queue a high-stakes action for human approval. Never auto-executes.

    Appends to human_approval_queue.jsonl. Returns {status, proposal_id}.
    action: e.g. "block", "propose_clawback"
    """
    proposal_id = str(uuid.uuid4())
    record = {
        "type": "high_stakes_proposal",
        "proposal_id": proposal_id,
        "transaction_id": transaction_id,
        "action": action,
        "justification": justification,
        "status": "pending_human_approval",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _append(_HUMAN_QUEUE, record)
    return {
        "status": "pending_human_approval",
        "proposal_id": proposal_id,
    }


# ---------------------------------------------------------------------------
# MCP registration
# ---------------------------------------------------------------------------

def register(mcp: FastMCP) -> None:
    mcp.tool()(request_evidence)
    mcp.tool()(flag_for_review)
    mcp.tool()(mark_compliant)
    mcp.tool()(notify_manager)
    mcp.tool()(propose_high_stakes_action)
