#!/usr/bin/env python3
"""Compile a raw policy text file into a draft CompiledPolicy and save it to disk.

Usage:
    python scripts/compile_policy.py --tenant-id meru-inc --policy-id <uuid>
"""
import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.agents.policy_compiler import compile_policy, diff_policies, print_diff  # noqa: E402
from app.services import policy_store  # noqa: E402

_POLICY_DIR = ROOT / "mcp_server" / "data" / "policies"


async def main(tenant_id: str, policy_id: str) -> None:
    txt_path = _POLICY_DIR / tenant_id / f"{policy_id}.txt"
    if not txt_path.exists():
        print(f"Error: policy text not found at {txt_path}", file=sys.stderr)
        sys.exit(1)

    policy_text = txt_path.read_text()
    print(f"Compiling policy {policy_id} for tenant '{tenant_id}'...")

    # Capture the current active version before compilation so we can diff after
    prev_active = policy_store.get_active(tenant_id)

    policy = await compile_policy(tenant_id, policy_id, policy_text)

    # save_draft assigns the correct next version number for this tenant
    policy_store.save_draft(policy)

    print(f"Saved → mcp_server/data/policies/{tenant_id}/{policy_id}.compiled.json")
    print(f"  version:    {policy.version}")
    print(f"  rules:      {len(policy.structured_rules)} structured")
    print(f"  refs:       {len(policy.natural_language_references)} natural language")
    print(f"  unsupported:{len(policy.unsupported_clauses)}")

    if prev_active is not None:
        diff = diff_policies(prev_active, policy)
        print_diff(diff, prev_active.version, policy.version)
    else:
        print("\n  (No previous active policy — this is the first compilation for this tenant.)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compile a policy text file into a draft CompiledPolicy.")
    parser.add_argument("--tenant-id", required=True, help="Tenant the policy belongs to")
    parser.add_argument("--policy-id", required=True, help="UUID of the policy text file")
    args = parser.parse_args()
    asyncio.run(main(args.tenant_id, args.policy_id))
