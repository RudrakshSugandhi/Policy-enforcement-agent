"""Eval harness — replay labeled transactions and report accuracy.

Usage:
    python scripts/run_eval.py           # full run (includes LLM cases)
    python scripts/run_eval.py --no-llm  # skip LLM-dependent cases (faster)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.services.orchestrator import evaluate  # noqa: E402

EVAL_SET = ROOT / "mcp_server" / "data" / "eval_set.json"

_COL = {
    "green":  "\033[32m",
    "red":    "\033[31m",
    "yellow": "\033[33m",
    "bold":   "\033[1m",
    "reset":  "\033[0m",
}


def _c(text: str, color: str) -> str:
    return f"{_COL[color]}{text}{_COL['reset']}"


def _pct(num: int, denom: int) -> str:
    if denom == 0:
        return "N/A"
    return f"{100 * num // denom}%"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run policy eval harness")
    parser.add_argument(
        "--no-llm", action="store_true",
        help="Skip non-deterministic (LLM-dependent) cases",
    )
    args = parser.parse_args()

    cases = json.loads(EVAL_SET.read_text())

    results: list[dict] = []
    skipped = 0

    for case in cases:
        txn_id = case["transaction_id"]
        is_llm = not case.get("deterministic", True)

        if args.no_llm and is_llm:
            skipped += 1
            continue

        try:
            decision = evaluate(txn_id)
            actual_verdict = decision.verdict.value
            actual_action = decision.action_taken.value
            agent_used = decision.agent_used
            error = None
        except Exception as exc:
            actual_verdict = "error"
            actual_action = "error"
            agent_used = False
            error = str(exc)

        accept = case.get("accept_verdicts", [case["expected_verdict"]])
        verdict_ok = actual_verdict in accept

        is_false_pass = (
            not verdict_ok
            and actual_verdict == "pass_through"
            and case["expected_verdict"] != "pass_through"
        )

        results.append({
            "txn_id":           txn_id,
            "label":            case["label"],
            "expected_verdict": case["expected_verdict"],
            "expected_action":  case["expected_action"],
            "actual_verdict":   actual_verdict,
            "actual_action":    actual_action,
            "verdict_ok":       verdict_ok,
            "agent_used":       agent_used,
            "deterministic":    case.get("deterministic", True),
            "gap":              case.get("gap", False),
            "false_pass":       is_false_pass,
            "error":            error,
            "notes":            case.get("notes", ""),
        })

    # ---------------------------------------------------------------------------
    # Results table
    # ---------------------------------------------------------------------------

    lw = 52
    header = f"{'Status':<6}  {'Label':<{lw}}  {'Expected':<16}  {'Actual':<16}  {'Type':<5}"
    sep = "-" * len(header)

    print()
    print(_c("Policy Eval Results", "bold"))
    print(sep)
    print(header)
    print(sep)

    for r in results:
        if r["verdict_ok"]:
            status = _c("PASS ", "green")
        elif r["gap"]:
            status = _c("GAP  ", "yellow")
        elif r["false_pass"]:
            status = _c("FP!! ", "red")
        else:
            status = _c("MISS ", "red")

        kind = "gap" if r["gap"] else ("llm" if not r["deterministic"] else "det")

        print(
            f"{status} {r['label'][:lw]:<{lw}}  "
            f"{r['expected_verdict']:<16}  "
            f"{r['actual_verdict']:<16}  "
            f"{kind:<5}"
        )
        if r["error"]:
            print(f"       ERROR: {r['error']}")

    print(sep)

    # ---------------------------------------------------------------------------
    # Metrics
    # ---------------------------------------------------------------------------

    det   = [r for r in results if r["deterministic"] and not r["gap"]]
    llm   = [r for r in results if not r["deterministic"] and not r["gap"]]
    gaps  = [r for r in results if r["gap"]]
    fps   = [r for r in results if r["false_pass"]]
    abst  = [r for r in results if r["actual_verdict"] == "abstain"]
    llm_h = [r for r in results if r["agent_used"]]

    det_ok  = sum(1 for r in det  if r["verdict_ok"])
    llm_ok  = sum(1 for r in llm  if r["verdict_ok"])
    gaps_ok = sum(1 for r in gaps if r["verdict_ok"])

    core_total = len(det) + len(llm)
    core_ok    = det_ok + llm_ok

    print()
    print(_c("Summary", "bold"))
    print(f"  Cases evaluated:             {len(results)}  (skipped: {skipped})")
    print(f"  Overall accuracy (excl. gaps): {core_ok}/{core_total}  ({_pct(core_ok, core_total)})")
    print()
    print(f"  Deterministic accuracy:      {det_ok}/{len(det)}  ({_pct(det_ok, len(det))})")
    if llm:
        print(f"  LLM accuracy:                {llm_ok}/{len(llm)}  ({_pct(llm_ok, len(llm))})")
    if gaps:
        print(f"  Adversarial gaps caught:     {gaps_ok}/{len(gaps)}  ({_pct(gaps_ok, len(gaps))})")
    print()
    print(f"  Handled by LLM agent:        {len(llm_h)}/{len(results)}  ({_pct(len(llm_h), len(results))})")
    print(f"  Abstain outcomes:            {len(abst)}/{len(results)}  ({_pct(len(abst), len(results))})")

    print(f"  False passes (wrong 'pass'): {len(fps)}/{len(results)}", end="")
    if fps:
        print(f"  {_c('<-- review these', 'red')}")
        for r in fps:
            print(f"    · ...{r['txn_id'][-4:]}  {r['label'][:60]}")
            print(f"      {r['notes'][:100]}")
    else:
        print(f"  {_c('✓ no silent miscoding', 'green')}")

    # Structuring pattern note
    structuring = [r for r in results if "Structuring" in r["label"]]
    if structuring:
        print()
        print(_c("  Structuring pattern (Phase 14 note):", "yellow"))
        print("  Three charges of $149/$148/$147 by emp-001 on consecutive days.")
        print("  Each is individually flagged for missing evidence. Batch-sweep")
        print("  detection to catch the $444 aggregate pattern is planned future")
        print("  work and out of MVP scope.")

    print()


if __name__ == "__main__":
    main()
