"""
MCP server entry point — stdio transport.

Run:
    conda activate reap-policy-agent
    python -m mcp_server.server
"""

from mcp.server.fastmcp import FastMCP
from mcp_server import registry

mcp = FastMCP("reap-policy-mcp")

registry.build(mcp)

if __name__ == "__main__":
    mcp.run(transport="stdio")
