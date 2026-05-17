"""Judgment agent — LLM fallback for ambiguous transactions.

Called by the orchestrator when the rule engine returns needs_judgment.
Runs a bounded tool-calling loop (max 5 tool calls) using the Meru policy's
natural language references, then emits a validated Decision.

Model: qwen2.5:7b-instruct via Ollama (sync client, temperature=0).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import ollama as ollama_lib
from pydantic import BaseModel, Field

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

# Cross-package imports — MCP tools live in mcp_server/
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mcp_server.tools.read_tools import (  # noqa: E402
    check_employee_calendar,
    convert_currency,
    get_active_policy,
    get_employee,
    get_employee_recent_transactions,
    get_receipt,
    get_transaction,
    get_vendor,
)
from mcp_server.tools.write_tools import (  # noqa: E402
    flag_for_review,
    mark_compliant,
    notify_manager,
    propose_high_stakes_action,
    request_evidence,
)
from mcp_server.tools.meta_tools import abstain  # noqa: E402

_OLLAMA_HOST = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
_MAX_TOOL_CALLS = 5


# ---------------------------------------------------------------------------
# Structured output schema (LLM fills this; Python adds remaining Decision fields)
# ---------------------------------------------------------------------------

class _JudgmentOutput(BaseModel):
    verdict: Verdict
    action_taken: ActionType
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)


_JUDGMENT_SCHEMA = _JudgmentOutput.model_json_schema()

# ---------------------------------------------------------------------------
# Tool registry — dispatch table + Ollama tool schemas
# ---------------------------------------------------------------------------

def _make_tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


_TOOLS: list[dict] = [
    _make_tool("get_receipt", "Return the receipt attached to a transaction, or null.",
               {"transaction_id": {"type": "string"}}, ["transaction_id"]),
    _make_tool("get_employee_recent_transactions",
               "Return transactions made by this employee in the last N days.",
               {"employee_id": {"type": "string"}, "days": {"type": "integer"}},
               ["employee_id"]),
    _make_tool("check_employee_calendar",
               "Return calendar events within 4 hours of a timestamp. "
               "Use this to check whether a meal or entertainment charge coincides with a client meeting.",
               {"employee_id": {"type": "string"}, "timestamp": {"type": "string"}},
               ["employee_id", "timestamp"]),
    _make_tool("convert_currency",
               "Convert an amount between USD, EUR, GBP, SGD.",
               {"amount": {"type": "number"}, "from_ccy": {"type": "string"}, "to_ccy": {"type": "string"}},
               ["amount", "from_ccy", "to_ccy"]),
    _make_tool("get_vendor",
               "Look up a vendor by ID or name.",
               {"vendor_id_or_name": {"type": "string"}}, ["vendor_id_or_name"]),
    _make_tool("request_evidence",
               "Ask the employee to upload missing evidence (receipt, attendee list, approval). "
               "Use this when you need more information before making a decision.",
               {
                   "transaction_id": {"type": "string"},
                   "items": {"type": "array", "items": {"type": "string"},
                             "description": "e.g. ['receipt', 'attendee_list', 'manager_approval']"},
                   "deadline_hours": {"type": "integer"},
               },
               ["transaction_id", "items"]),
    _make_tool("flag_for_review",
               "Queue the transaction for finance review. Use when the transaction is ambiguous "
               "but you have enough context to flag without escalating.",
               {
                   "transaction_id": {"type": "string"},
                   "reason": {"type": "string"},
                   "severity": {"type": "string", "enum": ["low", "medium", "high"]},
               },
               ["transaction_id", "reason"]),
    _make_tool("mark_compliant",
               "Record the transaction as policy-compliant. Only call this when you are confident "
               "the transaction passes all applicable policy checks.",
               {
                   "transaction_id": {"type": "string"},
                   "policy_version": {"type": "integer"},
               },
               ["transaction_id", "policy_version"]),
    _make_tool("notify_manager",
               "Escalate to the employee's manager. Use for escalate-level violations.",
               {
                   "transaction_id": {"type": "string"},
                   "manager_id": {"type": "string"},
                   "reason": {"type": "string"},
               },
               ["transaction_id", "manager_id", "reason"]),
    _make_tool("propose_high_stakes_action",
               "Queue a block or clawback for HUMAN APPROVAL. NEVER auto-executes. "
               "Use for clear hard-policy violations only.",
               {
                   "transaction_id": {"type": "string"},
                   "action": {"type": "string", "enum": ["block", "propose_clawback"]},
                   "justification": {"type": "string"},
               },
               ["transaction_id", "action", "justification"]),
    _make_tool("abstain",
               "Route to human review with no determination. Use when you cannot reach a "
               "confident conclusion (confidence < 0.5).",
               {
                   "transaction_id": {"type": "string"},
                   "reason": {"type": "string"},
               },
               ["transaction_id", "reason"]),
]

_TOOL_DISPATCH: dict[str, Any] = {
    "get_receipt": get_receipt,
    "get_employee_recent_transactions": get_employee_recent_transactions,
    "check_employee_calendar": check_employee_calendar,
    "convert_currency": convert_currency,
    "get_vendor": get_vendor,
    "get_transaction": get_transaction,
    "get_employee": get_employee,
    "request_evidence": request_evidence,
    "flag_for_review": flag_for_review,
    "mark_compliant": mark_compliant,
    "notify_manager": notify_manager,
    "propose_high_stakes_action": propose_high_stakes_action,
    "abstain": abstain,
}


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------

def _fmt(obj: Any) -> str:
    if obj is None:
        return "Not available."
    if isinstance(obj, BaseModel):
        return obj.model_dump_json(indent=2)
    return json.dumps(obj, indent=2, default=str)


def _build_system_prompt(
    txn: Transaction,
    policy: CompiledPolicy,
    receipt: Receipt | None,
    vendor: Vendor | None,
    employee: Employee | None,
    rules_fired: list[str],
) -> str:
    rule_map = {r.rule_id: r for r in policy.structured_rules}
    triggered = [
        f"  - {rule_map[rid].predicate.value}: \"{rule_map[rid].source_clause}\""
        for rid in rules_fired if rid in rule_map
    ]
    triggered_block = "\n".join(triggered) if triggered else "  (No specific rules — general ambiguity)"

    nl_refs = "\n".join(
        f"  [{ref.ref_id}] {ref.clause_text}"
        for ref in policy.natural_language_references
    ) or "  None."

    manager_id = (employee.manager_id or "finance-team") if employee else "finance-team"

    return f"""You are a policy compliance judgment agent for Reap, a financial spend management platform.
The deterministic rule engine could not make a final decision on this transaction. Your job is to evaluate it.

## TRANSACTION
{_fmt(txn)}

## EMPLOYEE
{_fmt(employee)}

## VENDOR
{_fmt(vendor)}

## RECEIPT
{_fmt(receipt)}

## KEY IDs (use exactly as shown when calling write tools)
- transaction_id: {txn.transaction_id}
- employee manager_id: {manager_id}
- policy_version: {policy.version}

## RULES THAT REQUIRED JUDGMENT
{triggered_block}

## NATURAL LANGUAGE POLICY REFERENCES (apply these with judgment)
{nl_refs}

## INSTRUCTIONS
1. Review the transaction details above.
2. Use the available tools to gather additional context (calendar, recent spend, receipt) if needed.
3. After gathering context, call exactly ONE write tool to take action:
   - mark_compliant        — transaction clearly passes policy
   - request_evidence      — you need more information before deciding
   - flag_for_review       — ambiguous but not clearly compliant
   - notify_manager        — clear escalation-level violation
   - propose_high_stakes_action — hard violation (block or clawback) for human approval
   - abstain               — you genuinely cannot determine compliance
4. Then provide your structured verdict JSON.

## CARDINAL RULES (NEVER VIOLATE)
- NEVER auto-execute block or clawback — always use propose_high_stakes_action (human must approve).
- If confidence < 0.5, call abstain() rather than guessing.
- Do not fabricate data — only use information from tools or the context above.
- Keep tool calls ≤ 5 total.
"""


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------

def _call_tool(name: str, args: dict) -> Any:
    fn = _TOOL_DISPATCH.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name!r}"}
    try:
        return fn(**args)
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def judge(
    transaction: Transaction,
    policy: CompiledPolicy,
    receipt: Receipt | None,
    vendor: Vendor | None,
    employee: Employee | None,
    rules_fired: list[str],
) -> Decision:
    """Run the LLM judgment loop and return a validated Decision.

    Falls back to abstain if the LLM produces an invalid verdict.
    """
    client = ollama_lib.Client(host=_OLLAMA_HOST)
    txn_id = str(transaction.transaction_id)

    messages: list[dict] = [
        {
            "role": "system",
            "content": _build_system_prompt(
                transaction, policy, receipt, vendor, employee, rules_fired
            ),
        },
        {
            "role": "user",
            "content": (
                "Please evaluate this transaction. "
                "Gather any context you need with tools, then take action and provide your verdict."
            ),
        },
    ]

    tool_calls_made = 0

    # --- Tool-calling loop ---
    for _ in range(_MAX_TOOL_CALLS + 1):  # +1 to allow final no-tool response
        response = client.chat(
            model=_MODEL,
            messages=messages,
            tools=_TOOLS,
            options={"temperature": 0},
        )

        # Append assistant turn
        assistant_msg: dict = {"role": "assistant", "content": response.message.content or ""}
        if response.message.tool_calls:
            assistant_msg["tool_calls"] = [
                {"function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in response.message.tool_calls
            ]
        messages.append(assistant_msg)

        if not response.message.tool_calls:
            break  # LLM finished deliberating

        for tc in response.message.tool_calls:
            if tool_calls_made >= _MAX_TOOL_CALLS:
                break
            result = _call_tool(tc.function.name, tc.function.arguments)
            messages.append({
                "role": "tool",
                "content": json.dumps(result, default=str) if result is not None else "null",
            })
            tool_calls_made += 1

    # --- Final structured verdict ---
    messages.append({
        "role": "user",
        "content": (
            "Now provide your final verdict as JSON. "
            "Fields: verdict, action_taken, rationale, confidence (0.0-1.0)."
        ),
    })

    final = client.chat(
        model=_MODEL,
        messages=messages,
        format=_JUDGMENT_SCHEMA,
        options={"temperature": 0},
    )

    try:
        output = _JudgmentOutput.model_validate_json(final.message.content)
    except Exception as exc:
        abstain(txn_id, f"Judgment agent produced invalid output: {exc}")
        output = _JudgmentOutput(
            verdict=Verdict.abstain,
            action_taken=ActionType.flag,
            rationale="LLM output failed schema validation — routed to human review.",
            confidence=0.0,
        )

    return Decision(
        decision_id=uuid4(),
        transaction_id=transaction.transaction_id,
        tenant_id=transaction.tenant_id,
        policy_version=policy.version,
        verdict=output.verdict,
        action_taken=output.action_taken,
        rule_path=rules_fired,
        agent_used=True,
        agent_rationale=output.rationale,
        confidence=output.confidence,
        timestamp=datetime.now(timezone.utc),
    )
