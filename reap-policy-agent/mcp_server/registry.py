from mcp.server.fastmcp import FastMCP
from mcp_server.tools import meta_tools, read_tools, write_tools

# Read tools (Phase 4 / 6):
#   get_transaction               get a single transaction by UUID
#   get_employee                  look up an employee by ID
#   get_vendor                    look up a vendor by ID or name
#   get_receipt                   get the receipt attached to a transaction
#   get_employee_recent_transactions  last N days of spend for an employee
#   check_employee_calendar       calendar events near a transaction timestamp
#   convert_currency              FX conversion between USD / EUR / GBP / SGD
#   get_active_policy             active compiled policy for a tenant
#   get_chart_of_accounts         valid expense categories for a tenant
#
# Write tools (Phase 8):
#   request_evidence              ask employee for receipt / approval docs
#   flag_for_review               queue transaction for finance review
#   mark_compliant                record transaction as policy-compliant
#   notify_manager                escalate to employee's manager
#   propose_high_stakes_action    queue block/clawback for human approval
#
# Meta tools (Phase 8):
#   abstain                       route to human review with no determination
#   validate_policy               schema-check a JSON array of CompiledRules
#   get_predicate_types           list supported predicate identifiers
#
# To add tools: implement register(mcp) in a new module and append it to _MODULES.
_MODULES = [read_tools, write_tools, meta_tools]


def build(mcp: FastMCP) -> None:
    for module in _MODULES:
        module.register(mcp)
