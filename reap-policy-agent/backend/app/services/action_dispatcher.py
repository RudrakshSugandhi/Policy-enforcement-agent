"""Action dispatcher — maps rule engine output to write-tool calls.

Takes the verdict + fired rules from rule_engine.evaluate() and dispatches
to the appropriate write/meta tools. Returns the list of action results so
the caller (orchestrator or test) can inspect what was dispatched.
"""
from __future__ import annotations

import sys
from pathlib import Path

from app.schemas import (
    ActionType,
    CompiledPolicy,
    Employee,
    Transaction,
    Verdict,
)

# Import write/meta tool functions directly (same process, no MCP round-trip)
_ROOT = Path(__file__).resolve().parents[3]   # reap-policy-agent/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mcp_server.tools.write_tools import (  # noqa: E402
    flag_for_review,
    mark_compliant,
    notify_manager,
    propose_high_stakes_action,
    request_evidence,
)
from mcp_server.tools.meta_tools import abstain  # noqa: E402

# Severity of each ActionType — used for documentation; dispatch logic below is explicit
_ACTION_SEVERITY: dict[ActionType, int] = {
    ActionType.pass_through:     0,
    ActionType.flag:             1,
    ActionType.request_evidence: 2,
    ActionType.escalate:         3,
    ActionType.propose_clawback: 4,
    ActionType.block:            5,
}


def dispatch(
    verdict: Verdict,
    rules_fired: list[str],
    missing_evidence: list[str],
    transaction: Transaction,
    policy: CompiledPolicy,
    employee: Employee | None,
) -> list[dict]:
    """Dispatch write-tool calls based on verdict and fired rules.

    Returns a list of result dicts — one per tool call made.

    Precedence for Verdict.fail (multiple rules may fire with different actions):
        block / propose_clawback  → propose_high_stakes_action
        escalate                  → notify_manager + flag_for_review(high)
        flag                      → flag_for_review(medium)
    """
    txn_id = str(transaction.transaction_id)
    results: list[dict] = []

    if verdict == Verdict.abstain:
        results.append(abstain(txn_id, "No applicable policy rule found for this transaction."))
        return results

    if verdict == Verdict.pass_through:
        results.append(mark_compliant(txn_id, policy.version))
        return results

    if verdict == Verdict.needs_evidence:
        items = missing_evidence or ["receipt"]
        results.append(request_evidence(txn_id, items))
        return results

    if verdict == Verdict.needs_judgment:
        rule_ids = ", ".join(rules_fired) if rules_fired else "unspecified"
        results.append(
            flag_for_review(
                txn_id,
                reason=f"Requires human judgment — rules: {rule_ids}",
                severity="medium",
            )
        )
        return results

    # --- Verdict.fail ---
    rule_map = {r.rule_id: r for r in policy.structured_rules}
    fired_rules = [rule_map[rid] for rid in rules_fired if rid in rule_map]
    actions = {r.action_on_violation for r in fired_rules}

    # Build a human-readable reason from source clauses (truncated)
    reason = "; ".join(r.source_clause[:80] for r in fired_rules) or "Policy violation."

    if ActionType.block in actions or ActionType.propose_clawback in actions:
        dominant = "block" if ActionType.block in actions else "propose_clawback"
        results.append(propose_high_stakes_action(txn_id, dominant, reason))

    if ActionType.escalate in actions:
        manager_id = (
            employee.manager_id
            if employee and employee.manager_id
            else "finance-team"
        )
        results.append(notify_manager(txn_id, manager_id, reason))
        results.append(flag_for_review(txn_id, reason, severity="high"))

    if (
        ActionType.flag in actions
        and ActionType.block not in actions
        and ActionType.propose_clawback not in actions
        and ActionType.escalate not in actions
    ):
        results.append(flag_for_review(txn_id, reason, severity="medium"))

    # Surface any missing evidence collected alongside a fail verdict
    if missing_evidence:
        results.append(request_evidence(txn_id, missing_evidence))

    return results
