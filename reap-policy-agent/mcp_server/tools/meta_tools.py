"""Meta tools — agent introspection and policy validation utilities.

Functions defined at module level for direct import by tests and the dispatcher.
"""
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Make the backend package importable when loaded standalone
_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.schemas import CompiledRule, PredicateType  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
_REVIEW_QUEUE = DATA / "review_queue.jsonl"


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

def abstain(transaction_id: str, reason: str) -> dict:
    """Route a transaction to human review without making a determination.

    Used when no applicable rule exists or the agent lacks sufficient context.
    Appends to review_queue.jsonl with severity=high.
    Returns {status, abstain_id}.
    """
    abstain_id = str(uuid.uuid4())
    record = {
        "type": "abstain",
        "abstain_id": abstain_id,
        "transaction_id": transaction_id,
        "reason": reason,
        "severity": "high",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _append(_REVIEW_QUEUE, record)
    position = _queue_length(_REVIEW_QUEUE)
    return {
        "status": "routed_to_human",
        "abstain_id": abstain_id,
        "queue_position": position,
    }


def validate_policy(rules_json: str) -> dict:
    """Validate that a JSON string is an array of well-formed CompiledRule objects.

    Returns {valid: bool, errors: list[str]}.
    """
    try:
        data = json.loads(rules_json)
    except json.JSONDecodeError as exc:
        return {"valid": False, "errors": [f"JSON parse error: {exc}"]}

    if not isinstance(data, list):
        return {"valid": False, "errors": ["Expected a JSON array of rule objects."]}

    errors: list[str] = []
    for i, item in enumerate(data):
        try:
            CompiledRule.model_validate(item)
        except Exception as exc:
            errors.append(f"Rule[{i}]: {exc}")

    return {"valid": len(errors) == 0, "errors": errors}


def get_predicate_types() -> list[str]:
    """Return all supported predicate type identifiers the rule engine understands."""
    return [p.value for p in PredicateType]


# ---------------------------------------------------------------------------
# MCP registration
# ---------------------------------------------------------------------------

def register(mcp: FastMCP) -> None:
    mcp.tool()(abstain)
    mcp.tool()(validate_policy)
    mcp.tool()(get_predicate_types)
