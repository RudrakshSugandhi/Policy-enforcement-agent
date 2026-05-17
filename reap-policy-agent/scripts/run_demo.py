#!/usr/bin/env python3
"""Demo: evaluate all 10 mock transactions and print a verdict table.

Usage:
    conda activate reap-policy-agent
    python scripts/run_demo.py

Requires Ollama to be running only if a policy needs to be compiled.
The demo seeds a clean policy in memory if no active meru-inc policy exists.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.schemas import (
    ActionType,
    CompiledPolicy,
    CompiledRule,
    NaturalLanguageReference,
    PolicyStatus,
    PredicateType,
    UnsupportedClause,
)
from app.services import policy_store
from app.services.orchestrator import evaluate

# ---------------------------------------------------------------------------
# Demo policy — clean 4-rule subset of the Meru v1 policy
# ---------------------------------------------------------------------------

_DEMO_UUID = "dddddddd-0000-0000-0000-000000000001"

_DEMO_RULES: list[CompiledRule] = [
    CompiledRule(
        rule_id="rule-001",
        predicate=PredicateType.amount_requires_receipt,
        parameters={"threshold": 75, "currency": "USD"},
        applies_when=None,
        evidence_required=["receipt"],
        action_on_violation=ActionType.request_evidence,
        source_clause="Receipts are required for any expense over 75 USD.",
    ),
    CompiledRule(
        rule_id="rule-002",
        predicate=PredicateType.hotel_star_max,
        parameters={"max_stars": 4},
        applies_when=None,
        evidence_required=[],
        action_on_violation=ActionType.flag,
        source_clause="Hotels must be four stars or below.",
    ),
    CompiledRule(
        rule_id="rule-003",
        predicate=PredicateType.vendor_blocklist,
        parameters={"vendors": ["Competitor Corp", "RivalCo"]},
        applies_when=None,
        evidence_required=[],
        action_on_violation=ActionType.block,
        source_clause="Purchases from Competitor Corp and RivalCo are not permitted.",
    ),
    CompiledRule(
        rule_id="rule-004",
        predicate=PredicateType.category_pre_approval,
        parameters={
            "categories": ["SaaS subscriptions"],
            "approval_from": "department head",
        },
        applies_when="amount > 500 USD per month",
        evidence_required=["manager_approval"],
        action_on_violation=ActionType.escalate,
        source_clause=(
            "SaaS subscriptions above 500 USD per month require pre-approval "
            "from the department head before purchase."
        ),
    ),
]

_DEMO_NL_REFS: list[NaturalLanguageReference] = [
    NaturalLanguageReference(
        ref_id="ref-001",
        clause_text=(
            "Alcohol is reimbursable only when clients are present "
            "and must not exceed 20% of the total bill."
        ),
        applies_to_transaction_types=["meal", "entertainment"],
        keywords=["alcohol", "clients present", "client dinner", "20%"],
    ),
]

_DEMO_UNSUPPORTED: list[UnsupportedClause] = [
    UnsupportedClause(
        clause_text="Quarterly expense reports must be submitted to the board.",
        reason="Governance obligation — not a transaction-level rule.",
    ),
]


def _ensure_demo_policy() -> CompiledPolicy:
    """Activate the demo policy if no vendor-blocklist-capable policy is active."""
    active = policy_store.get_active("meru-inc")
    if active is not None:
        predicates = {r.predicate.value for r in active.structured_rules}
        if "vendor_blocklist" in predicates and "hotel_star_max" in predicates:
            print(f"[setup] Active policy v{active.version} — reusing.")
            return active

    print("[setup] Seeding demo policy for meru-inc …")
    draft = CompiledPolicy(
        policy_id=UUID(_DEMO_UUID),
        tenant_id="meru-inc",
        version=1,                       # save_draft overrides this
        status=PolicyStatus.draft,
        structured_rules=_DEMO_RULES,
        natural_language_references=_DEMO_NL_REFS,
        unsupported_clauses=_DEMO_UNSUPPORTED,
        created_at=datetime.now(timezone.utc),
    )
    policy_store.save_draft(draft)
    policy_store.approve(_DEMO_UUID, reviewer_id="demo-script")
    active = policy_store.get_active("meru-inc")
    print(f"[setup] Demo policy activated as v{active.version}.")
    return active


# ---------------------------------------------------------------------------
# Transactions to evaluate
# ---------------------------------------------------------------------------

_TRANSACTION_IDS = [
    "a1b2c3d4-0001-0001-0001-000000000001",   # Marriott Hotels $220 — receipt attached
    "a1b2c3d4-0002-0002-0002-000000000002",   # Zoom $299 — no receipt
    "a1b2c3d4-0003-0003-0003-000000000003",   # Grab $42 SGD — under threshold
    "a1b2c3d4-0004-0004-0004-000000000004",   # British Airways $580 — receipt attached
    "a1b2c3d4-0005-0005-0005-000000000005",   # Capital Grille $68 — under threshold, receipt
    "a1b2c3d4-0006-0006-0006-000000000006",   # Nobu London $180 — no receipt
    "a1b2c3d4-0007-0007-0007-000000000007",   # Competitor Corp — blocklisted
    "a1b2c3d4-0008-0008-0008-000000000008",   # Capital Grille $320 — no receipt
    "a1b2c3d4-0009-0009-0009-000000000009",   # Four Seasons $450 — hotel star check
    "a1b2c3d4-0010-0010-0010-000000000010",   # Salesforce $1200 — SaaS pre-approval
]

_SCENARIO_LABELS = [
    "receipt attached, 4-star hotel",
    "SaaS under $500 threshold",
    "transport under receipt threshold",
    "flight with receipt",
    "meal under receipt threshold, receipt",
    "dinner, no receipt",
    "vendor on blocklist",
    "ambiguous client dinner",
    "hotel star check",
    "SaaS above $500, pre-approval needed",
]


# ---------------------------------------------------------------------------
# Table rendering
# ---------------------------------------------------------------------------

def _col(s: str, width: int) -> str:
    s = str(s)
    return s[:width].ljust(width)


def _print_table(rows: list[dict]) -> None:
    cols = [
        ("TXN (last 4)", 12),
        ("Merchant", 22),
        ("Amount", 12),
        ("Verdict", 18),
        ("Action Taken", 22),
        ("Rules Fired", 22),
        ("Ver", 4),
    ]
    sep = "+" + "+".join("-" * (w + 2) for _, w in cols) + "+"
    header = "|" + "|".join(f" {_col(c, w)} " for c, w in cols) + "|"
    print(sep)
    print(header)
    print(sep)
    for row in rows:
        line = "|" + "|".join(
            f" {_col(row[k], w)} " for (k, _), (_, w) in zip(
                [(c, None) for c, _ in cols], cols
            )
        ) + "|"
        print(line)
    print(sep)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    policy = _ensure_demo_policy()
    print(f"\nEvaluating {len(_TRANSACTION_IDS)} transactions against Meru policy "
          f"v{policy.version} ({len(policy.structured_rules)} rules)\n")

    rows: list[dict] = []
    errors: list[str] = []

    for txn_id, label in zip(_TRANSACTION_IDS, _SCENARIO_LABELS):
        try:
            decision = evaluate(txn_id)
            rules = ", ".join(decision.rule_path) if decision.rule_path else "—"
            rows.append({
                "TXN (last 4)":  txn_id[-4:],
                "Merchant":      label[:22],
                "Amount":        f"txn {txn_id[-4:]}",
                "Verdict":       decision.verdict.value,
                "Action Taken":  decision.action_taken.value,
                "Rules Fired":   rules,
                "Ver":           str(decision.policy_version),
            })
        except Exception as exc:
            errors.append(f"  {txn_id[-4:]}: {exc}")

    # Re-fetch amounts from read tools for display
    from mcp_server.tools.read_tools import get_transaction
    for i, (txn_id, row) in enumerate(zip(_TRANSACTION_IDS, rows)):
        raw = get_transaction(txn_id)
        row["Amount"] = f"{raw['amount']} {raw['currency']}"
        row["Merchant"] = raw["merchant_name"][:22]

    _print_table(rows)

    if errors:
        print("\nErrors:")
        for e in errors:
            print(e)

    # Summary counts
    verdicts = [r["Verdict"] for r in rows]
    print(f"\nSummary: {verdicts.count('pass_through')} pass  "
          f"{verdicts.count('needs_evidence')} evidence  "
          f"{verdicts.count('needs_judgment')} judgment  "
          f"{verdicts.count('fail')} fail  "
          f"{verdicts.count('abstain')} abstain")
    print(f"Audit log: {sum(1 for _ in open(ROOT / 'mcp_server/data/audit_log.jsonl'))} total entries\n")


if __name__ == "__main__":
    main()
