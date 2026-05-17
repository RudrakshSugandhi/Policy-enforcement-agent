from mcp.server.fastmcp import FastMCP
from mcp_server.tools import read_tools

# All registered tools (Phase 4 — read tools):
#   get_transaction               get a single transaction by UUID
#   get_employee                  look up an employee by ID
#   get_vendor                    look up a vendor by ID or name
#   get_receipt                   get the receipt attached to a transaction
#   get_employee_recent_transactions  last N days of spend for an employee
#   check_employee_calendar       calendar events near a transaction timestamp
#   convert_currency              FX conversion between USD / EUR / GBP / SGD
#   get_active_policy             active compiled policy for a tenant (None until Phase 5)
#   get_chart_of_accounts         valid expense categories for a tenant
#
# To add tools: implement register(mcp) in a new module and append it to _MODULES.
_MODULES = [read_tools]


def build(mcp: FastMCP) -> None:
    for module in _MODULES:
        module.register(mcp)
