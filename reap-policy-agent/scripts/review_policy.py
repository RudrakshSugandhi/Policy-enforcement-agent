#!/usr/bin/env python3
"""Interactive CLI to review a compiled draft policy and approve it.

Usage:
    python scripts/review_policy.py --policy-id <uuid>

Flow:
    1. Loads the draft CompiledPolicy from disk.
    2. Walks through each structured rule, NL reference, and unsupported clause.
    3. Prompts the reviewer to approve / edit / reject each item.
    4. Collects reviewer name/ID and saves the approved policy back to disk.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.agents.policy_compiler import diff_policies, print_diff  # noqa: E402
from app.schemas import (  # noqa: E402
    ActionType,
    CompiledPolicy,
    CompiledRule,
    NaturalLanguageReference,
    PolicyStatus,
    UnsupportedClause,
)
from app.services import policy_store  # noqa: E402

_POLICY_DIR = ROOT / "mcp_server" / "data" / "policies"
_SEP = "─" * 62
_ACTIONS = [a.value for a in ActionType]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_compiled_policy(policy_id: str) -> Path:
    for path in _POLICY_DIR.glob(f"*/{policy_id}.compiled.json"):
        return path
    raise FileNotFoundError(
        f"No compiled policy found for ID {policy_id!r}.\n"
        f"Run compile_policy.py first."
    )


def _ask(prompt: str, valid: set[str]) -> str:
    while True:
        answer = input(prompt).strip().lower()
        if answer in valid:
            return answer
        print(f"    Please enter one of: {', '.join(sorted(valid))}")


def _header(title: str) -> None:
    print(f"\n{_SEP}")
    print(f"  {title}")
    print(_SEP)


# ---------------------------------------------------------------------------
# Section reviewers
# ---------------------------------------------------------------------------

def _review_rule(rule: CompiledRule, idx: int, total: int) -> CompiledRule | None:
    """Returns the (possibly edited) rule, or None if rejected."""
    _header(f"STRUCTURED RULE  [{idx}/{total}]  {rule.rule_id}")
    print(f"\n  Source clause:  \"{rule.source_clause}\"")
    print(f"\n  Predicate:      {rule.predicate.value}")
    print(f"  Parameters:     {json.dumps(rule.parameters)}")
    print(f"  Action:         {rule.action_on_violation.value}")
    if rule.evidence_required:
        print(f"  Evidence:       {', '.join(rule.evidence_required)}")
    if rule.applies_when:
        print(f"  Condition:      {rule.applies_when}")

    choice = _ask("\n  [a]pprove  [e]dit  [r]eject  [s]kip › ", {"a", "e", "r", "s"})

    if choice in ("a", "s"):
        return rule

    if choice == "r":
        print(f"  Rule {rule.rule_id} rejected and removed from policy.")
        return None

    # --- edit ---
    updates: dict = {}

    print(f"\n  Available actions: {' | '.join(_ACTIONS)}")
    new_action = input(f"  New action (Enter to keep '{rule.action_on_violation.value}'): ").strip()
    if new_action:
        try:
            updates["action_on_violation"] = ActionType(new_action)
        except ValueError:
            print(f"  Unknown action '{new_action}' — keeping original.")

    print(f"  Current parameters: {json.dumps(rule.parameters)}")
    new_params = input("  New parameters as JSON (Enter to keep): ").strip()
    if new_params:
        try:
            updates["parameters"] = json.loads(new_params)
        except json.JSONDecodeError as exc:
            print(f"  Invalid JSON ({exc}) — keeping original.")

    return rule.model_copy(update=updates) if updates else rule


def _review_ref(
    ref: NaturalLanguageReference, idx: int, total: int
) -> NaturalLanguageReference | None:
    """Returns the (possibly edited) reference, or None if rejected."""
    _header(f"NATURAL LANGUAGE REF  [{idx}/{total}]  {ref.ref_id}")
    print(f"\n  Clause text:    \"{ref.clause_text}\"")
    print(f"\n  Applies to:     {', '.join(ref.applies_to_transaction_types)}")
    print(f"  Keywords:       {', '.join(ref.keywords)}")

    choice = _ask("\n  [a]pprove  [e]dit  [r]eject › ", {"a", "e", "r"})

    if choice == "a":
        return ref

    if choice == "r":
        print(f"  Ref {ref.ref_id} rejected and removed from policy.")
        return None

    # --- edit ---
    updates: dict = {}

    new_kw = input(f"  Keywords (comma-separated, Enter to keep): ").strip()
    if new_kw:
        updates["keywords"] = [k.strip() for k in new_kw.split(",") if k.strip()]

    new_types = input(f"  Transaction types (comma-separated, Enter to keep): ").strip()
    if new_types:
        updates["applies_to_transaction_types"] = [
            t.strip() for t in new_types.split(",") if t.strip()
        ]

    return ref.model_copy(update=updates) if updates else ref


def _review_unsupported(clause: UnsupportedClause, idx: int, total: int) -> str:
    """Returns 'i' (ignore) or 'm' (mark_for_future)."""
    _header(f"UNSUPPORTED CLAUSE  [{idx}/{total}]")
    print(f"\n  Clause:  \"{clause.clause_text}\"")
    print(f"  Reason:  {clause.reason}")
    return _ask("\n  [i]gnore  [m]ark_for_future › ", {"i", "m"})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(policy_id: str) -> None:
    try:
        path = _find_compiled_policy(policy_id)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    policy = CompiledPolicy.model_validate_json(path.read_text())

    if policy.status != PolicyStatus.draft:
        print(f"Warning: policy status is already '{policy.status.value}'. Continuing anyway.")

    print(f"\n  Policy:   {policy.policy_id}")
    print(f"  Tenant:   {policy.tenant_id}")
    print(f"  Version:  {policy.version}  (status: {policy.status.value})")
    print(f"  Compiled: {policy.created_at.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"\n  {len(policy.structured_rules)} structured rules")
    print(f"  {len(policy.natural_language_references)} natural language references")
    print(f"  {len(policy.unsupported_clauses)} unsupported clauses")

    # Show diff against the previously active version (if one exists)
    prev_active = policy_store.get_active(policy.tenant_id)
    if prev_active is not None and prev_active.policy_id != policy.policy_id:
        diff = diff_policies(prev_active, policy)
        print_diff(diff, prev_active.version, policy.version)
    else:
        print("\n  (No previous active policy — first compilation for this tenant.)\n")

    input("Press Enter to begin review…")

    # --- Structured rules ---
    approved_rules: list[CompiledRule] = []
    rejected_rules = 0

    for i, rule in enumerate(policy.structured_rules, 1):
        result = _review_rule(rule, i, len(policy.structured_rules))
        if result is None:
            rejected_rules += 1
        else:
            approved_rules.append(result)

    # --- Natural language references ---
    approved_refs: list[NaturalLanguageReference] = []
    rejected_refs = 0

    for i, ref in enumerate(policy.natural_language_references, 1):
        result = _review_ref(ref, i, len(policy.natural_language_references))
        if result is None:
            rejected_refs += 1
        else:
            approved_refs.append(result)

    # --- Unsupported clauses ---
    marked_for_future: list[UnsupportedClause] = []
    ignored_count = 0

    for i, clause in enumerate(policy.unsupported_clauses, 1):
        decision = _review_unsupported(clause, i, len(policy.unsupported_clauses))
        if decision == "m":
            marked_for_future.append(clause)
        else:
            ignored_count += 1

    # --- Summary ---
    _header("REVIEW SUMMARY")
    print(f"\n  Structured rules:   {len(approved_rules)} kept, {rejected_rules} rejected")
    print(f"  NL references:      {len(approved_refs)} kept, {rejected_refs} rejected")
    print(f"  Unsupported:        {ignored_count} ignored, {len(marked_for_future)} marked for future")

    if marked_for_future:
        print(f"\n  Clauses marked for future implementation:")
        for clause in marked_for_future:
            print(f"    • {clause.clause_text[:72]}")

    print()
    reviewer = input("  Reviewer name or ID: ").strip() or "unknown"

    approved = policy.model_copy(update={
        "status": PolicyStatus.approved,
        "structured_rules": approved_rules,
        "natural_language_references": approved_refs,
        "approved_by": reviewer,
        "approved_at": datetime.now(timezone.utc),
        "version": policy.version + 1,
    })

    path.write_text(approved.model_dump_json(indent=2))

    print(f"\n  Approved as v{approved.version}  |  reviewer: {approved.approved_by}")
    print(f"  Saved → {path.relative_to(ROOT)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Review a compiled draft policy and approve it.")
    parser.add_argument("--policy-id", required=True, help="UUID of the compiled policy")
    args = parser.parse_args()
    try:
        main(args.policy_id)
    except KeyboardInterrupt:
        print("\n\nReview cancelled.")
        sys.exit(0)
