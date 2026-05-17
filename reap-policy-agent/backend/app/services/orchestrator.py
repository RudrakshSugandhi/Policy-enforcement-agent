"""Orchestrator — end-to-end evaluate(transaction_id) -> Decision.

Phase 10 happy path (deterministic only):
  1. Load transaction via read tools
  2. Load employee, vendor, receipt, active policy
  3. Run rule engine
  4. Dispatch action (needs_judgment stubbed to flag_for_review)
  5. Build Decision and write to audit log
  6. Return Decision
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.schemas import (
    ActionType,
    CompiledPolicy,
    Decision,
    Employee,
    Receipt,
    Transaction,
    Vendor,
    Verdict,
)
from app.services import policy_store
from app.services.rule_engine import evaluate as _rule_eval
from app.services.action_dispatcher import dispatch as _dispatch

# Cross-package imports — read/write tools live in mcp_server/
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mcp_server.tools.read_tools import (  # noqa: E402
    get_employee,
    get_receipt,
    get_transaction,
    get_vendor,
)
from mcp_server.tools.write_tools import flag_for_review  # noqa: E402

_AUDIT_LOG = _ROOT / "mcp_server" / "data" / "audit_log.jsonl"

# ---------------------------------------------------------------------------
# Verdict → action mapping helpers
# ---------------------------------------------------------------------------

_VERDICT_ACTION: dict[Verdict, ActionType] = {
    Verdict.pass_through:   ActionType.pass_through,
    Verdict.needs_evidence: ActionType.request_evidence,
    Verdict.needs_judgment: ActionType.flag,
    Verdict.abstain:        ActionType.flag,
}

_VERDICT_CONFIDENCE: dict[Verdict, float] = {
    Verdict.pass_through:   1.0,
    Verdict.fail:           1.0,
    Verdict.needs_evidence: 0.9,
    Verdict.needs_judgment: 0.0,
    Verdict.abstain:        0.0,
}

_ACTION_SEVERITY = [
    ActionType.pass_through,
    ActionType.flag,
    ActionType.request_evidence,
    ActionType.escalate,
    ActionType.propose_clawback,
    ActionType.block,
]


def _action_for_fail(rules_fired: list[str], policy: CompiledPolicy) -> ActionType:
    """Return the most severe action_on_violation among all fired rules."""
    rule_map = {r.rule_id: r for r in policy.structured_rules}
    best = ActionType.flag
    for rid in rules_fired:
        rule = rule_map.get(rid)
        if rule and _ACTION_SEVERITY.index(rule.action_on_violation) > _ACTION_SEVERITY.index(best):
            best = rule.action_on_violation
    return best


def _action_taken(
    verdict: Verdict, rules_fired: list[str], policy: CompiledPolicy
) -> ActionType:
    if verdict == Verdict.fail:
        return _action_for_fail(rules_fired, policy)
    return _VERDICT_ACTION.get(verdict, ActionType.flag)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def _append_audit(decision: Decision) -> None:
    with _AUDIT_LOG.open("a") as f:
        f.write(json.dumps(decision.model_dump(mode="json")) + "\n")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(transaction_id: str) -> Decision:
    """Evaluate a single transaction end-to-end and return a Decision.

    Raises ValueError if the transaction cannot be found.
    """
    # 1. Load transaction
    raw = get_transaction(transaction_id)
    if "error" in raw:
        raise ValueError(f"Transaction not found: {transaction_id}")
    txn = Transaction.model_validate(raw)

    # 2. Load context
    policy = policy_store.get_active(txn.tenant_id)

    employee_raw = get_employee(txn.employee_id)
    employee = Employee.model_validate(employee_raw) if employee_raw else None

    vendor: Vendor | None = None
    if txn.vendor_id:
        vendor_raw = get_vendor(txn.vendor_id)
        vendor = Vendor.model_validate(vendor_raw) if vendor_raw else None

    receipt_raw = get_receipt(transaction_id)
    receipt = Receipt.model_validate(receipt_raw) if receipt_raw else None

    # 3. Handle missing policy — abstain
    if policy is None:
        decision = Decision(
            decision_id=uuid4(),
            transaction_id=txn.transaction_id,
            tenant_id=txn.tenant_id,
            policy_version=0,
            verdict=Verdict.abstain,
            action_taken=ActionType.flag,
            rule_path=[],
            agent_used=False,
            confidence=0.0,
            timestamp=datetime.now(timezone.utc),
            agent_rationale="No active policy found for tenant.",
        )
        _append_audit(decision)
        return decision

    # 4. Run rule engine
    verdict, rules_fired, missing_evidence = _rule_eval(txn, policy, receipt, vendor, employee)

    # 5. Dispatch
    if verdict == Verdict.needs_judgment:
        # Phase 11: LLM judgment agent handles context gathering + action dispatch internally
        from app.agents.judgment_agent import judge
        decision = judge(txn, policy, receipt, vendor, employee, rules_fired)
        _append_audit(decision)
        return decision

    _dispatch(verdict, rules_fired, missing_evidence, txn, policy, employee)

    # 6. Build and persist Decision
    decision = Decision(
        decision_id=uuid4(),
        transaction_id=txn.transaction_id,
        tenant_id=txn.tenant_id,
        policy_version=policy.version,
        verdict=verdict,
        action_taken=_action_taken(verdict, rules_fired, policy),
        rule_path=rules_fired,
        agent_used=False,
        confidence=_VERDICT_CONFIDENCE.get(verdict, 0.5),
        timestamp=datetime.now(timezone.utc),
    )
    _append_audit(decision)
    return decision
