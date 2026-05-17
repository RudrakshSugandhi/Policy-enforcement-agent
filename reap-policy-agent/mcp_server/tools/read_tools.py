import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from mcp_server.schemas.tool_io import GetTransactionInput, GetTransactionOutput

DATA = Path(__file__).resolve().parent.parent / "data"

# all mock data loaded once at import time — replaced by DB calls in production
_transactions: list[dict] = json.loads((DATA / "transactions.json").read_text())
_employees: list[dict] = json.loads((DATA / "employees.json").read_text())
_vendors: list[dict] = json.loads((DATA / "vendors.json").read_text())
_receipts: list[dict] = json.loads((DATA / "receipts.json").read_text())
_calendar: dict = json.loads((DATA / "calendar.json").read_text())

# FX rates relative to USD — hardcoded for the demo
_FX: dict[str, float] = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "SGD": 1.35,
}

_CHART_OF_ACCOUNTS: dict[str, list[str]] = {
    "meru-inc": [
        "Travel - Airfare",
        "Travel - Hotel",
        "Travel - Ground Transport",
        "Meals - Solo",
        "Meals - Client Entertainment",
        "Software & Subscriptions",
        "Office Supplies",
        "Team Events",
        "Professional Services",
        "Training & Development",
    ]
}


def _clean(row: dict) -> dict:
    # strip internal annotation keys (e.g. _scenario) before returning over the wire
    return {k: v for k, v in row.items() if not k.startswith("_")}


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def get_transaction(transaction_id: str) -> dict:
        """Return a single transaction record by its UUID."""
        try:
            req = GetTransactionInput(transaction_id=UUID(transaction_id))
        except ValueError as e:
            return {"error": f"Invalid UUID: {e}", "transaction_id": transaction_id}
        for row in _transactions:
            if row["transaction_id"] == str(req.transaction_id):
                return GetTransactionOutput.model_validate(row).model_dump(mode="json")
        return {"error": "Transaction not found", "transaction_id": str(req.transaction_id)}

    @mcp.tool()
    def get_employee(employee_id: str) -> dict | None:
        """Return an employee record by employee_id, or None if not found."""
        for row in _employees:
            if row["employee_id"] == employee_id:
                return row
        return None

    @mcp.tool()
    def get_vendor(vendor_id_or_name: str) -> dict | None:
        """Return a vendor by vendor_id or name (case-insensitive), or None if not found."""
        needle = vendor_id_or_name.lower()
        for row in _vendors:
            if row["vendor_id"] == vendor_id_or_name or row["name"].lower() == needle:
                return row
        return None

    @mcp.tool()
    def get_receipt(transaction_id: str) -> dict | None:
        """Return the receipt attached to a transaction, or None if no receipt exists."""
        for row in _receipts:
            if row["transaction_id"] == transaction_id:
                return row
        return None

    @mcp.tool()
    def get_employee_recent_transactions(employee_id: str, days: int = 30) -> list[dict]:
        """Return all transactions by an employee within the last N days.

        Uses the most recent transaction timestamp as the anchor (not wall clock)
        so results are stable against static mock data.
        """
        emp_txns = [t for t in _transactions if t["employee_id"] == employee_id]
        if not emp_txns:
            return []
        timestamps = [
            datetime.fromisoformat(t["timestamp"].replace("Z", "+00:00"))
            for t in emp_txns
        ]
        anchor = max(timestamps)
        cutoff = anchor - timedelta(days=days)
        return [
            _clean(t) for t in emp_txns
            if datetime.fromisoformat(t["timestamp"].replace("Z", "+00:00")) >= cutoff
        ]

    @mcp.tool()
    def check_employee_calendar(employee_id: str, timestamp: str) -> list[dict]:
        """Return calendar events for an employee within 4 hours of the given timestamp.

        Used by the judgment agent to check whether a meal or entertainment charge
        coincides with a client meeting.
        """
        events = _calendar.get(employee_id, [])
        if not events:
            return []
        try:
            target = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return []
        window = timedelta(hours=4)
        return [
            e for e in events
            if abs(datetime.fromisoformat(e["start"].replace("Z", "+00:00")) - target) <= window
        ]

    @mcp.tool()
    def convert_currency(amount: float, from_ccy: str, to_ccy: str) -> float:
        """Convert an amount between currencies using hardcoded demo rates.

        Supported: USD, EUR, GBP, SGD.
        """
        f = _FX.get(from_ccy.upper())
        t = _FX.get(to_ccy.upper())
        if f is None:
            raise ValueError(f"Unsupported currency: {from_ccy}")
        if t is None:
            raise ValueError(f"Unsupported currency: {to_ccy}")
        return round(amount / f * t, 2)

    @mcp.tool()
    def get_active_policy(tenant_id: str) -> dict | None:
        """Return the active compiled policy for a tenant.

        Returns None until Phase 5 (policy compiler) produces a compiled policy.
        The orchestrator treats None as 'no structured rules available — use NL judgment only'.
        """
        return None

    @mcp.tool()
    def get_chart_of_accounts(tenant_id: str) -> list[str]:
        """Return the list of valid expense categories for a tenant."""
        return _CHART_OF_ACCOUNTS.get(tenant_id, [])
