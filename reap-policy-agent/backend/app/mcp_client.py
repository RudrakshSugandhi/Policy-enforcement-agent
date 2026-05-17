"""
Thin async MCP client.

Spawns the MCP server as a subprocess over stdio and exposes call_tool().
The backend uses this to request data from the MCP server without knowing
how the server stores or fetches it.

Usage:
    async with MCPClient() as client:
        result = await client.call_tool("get_transaction", {"transaction_id": "..."})
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# path to the mcp_server package from the repo root
_MCP_SERVER_DIR = Path(__file__).resolve().parent.parent.parent / "mcp_server"


class MCPClient:
    """Async context manager that owns a single MCP server subprocess."""

    def __init__(self) -> None:
        self._session: ClientSession | None = None
        self._cm = None

    async def __aenter__(self) -> "MCPClient":
        params = StdioServerParameters(
            command="python",
            args=["-m", "mcp_server.server"],
            cwd=str(_MCP_SERVER_DIR.parent),  # run from reap-policy-agent/
        )
        self._cm = stdio_client(params)
        read, write = await self._cm.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
        return self

    async def __aexit__(self, *exc) -> None:
        if self._session:
            await self._session.__aexit__(*exc)
        if self._cm:
            await self._cm.__aexit__(*exc)

    async def call_tool(self, name: str, args: dict[str, Any]) -> Any:
        """Call a named MCP tool and return the parsed result.

        FastMCP serialises list returns as one TextContent block per item,
        so we collect all blocks and reconstruct the list. Plain strings that
        are not valid JSON are returned as-is.
        """
        import json

        def _decode(text: str) -> Any:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text  # plain string value (e.g. a category name)

        if self._session is None:
            raise RuntimeError("MCPClient must be used as an async context manager")
        result = await self._session.call_tool(name, args)
        if not result.content:
            return None
        blocks = [b for b in result.content if hasattr(b, "text") and b.text.strip()]
        if not blocks:
            return None
        if len(blocks) == 1:
            return _decode(blocks[0].text)
        return [_decode(b.text) for b in blocks]


@asynccontextmanager
async def mcp_client():
    """Convenience async context manager for one-off calls."""
    async with MCPClient() as client:
        yield client
