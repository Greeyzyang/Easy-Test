import os
from typing import List, Any, Optional
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Global singleton - initialized once, reused across all AgentService instances
_mcp_service_instance: Optional["MCPBrowserService"] = None


class MCPBrowserService:
    """
    Loads and manages MCP server tools from the database.
    Tools are lazily loaded and cached per server process lifetime.
    """

    def __init__(self):
        self._tools: Optional[List[Any]] = None
        self._client = None
        self._loaded = False

    async def get_mcp_tools(self) -> List[Any]:
        """Load all enabled MCP server tools from DB. Returns empty list on failure."""
        if self._loaded:
            return self._tools or []

        try:
            from sqlalchemy import select
            from app.database import async_session_maker
            from app.models.mcp_server import MCPServer

            async with async_session_maker() as session:
                result = await session.execute(
                    select(MCPServer).where(MCPServer.enabled == True)
                )
                servers = result.scalars().all()

            if not servers:
                logger.info("No enabled MCP servers found in database.")
                self._tools = []
                self._loaded = True
                return []

            logger.info(f"Loading {len(servers)} enabled MCP server(s): {[s.name for s in servers]}")

            connections = {}
            for server in servers:
                if server.transport == "stdio":
                    if not server.command:
                        logger.warning(f"MCP Server '{server.name}' has stdio transport but no command, skipping.")
                        continue
                    connections[server.name] = {
                        "transport": "stdio",
                        "command": server.command,
                        "args": server.args or [],
                        "env": server.env or {}
                    }
                elif server.transport in ("http", "sse"):
                    if not server.url:
                        logger.warning(f"MCP Server '{server.name}' has {server.transport} transport but no URL, skipping.")
                        continue
                    connections[server.name] = {
                        "transport": server.transport,
                        "url": server.url
                    }
                else:
                    logger.warning(f"Unknown transport '{server.transport}' for MCP Server '{server.name}', skipping.")

            if not connections:
                logger.warning("No valid MCP server connections could be built.")
                self._tools = []
                self._loaded = True
                return []

            try:
                from langchain_mcp_adapters.client import MultiServerMCPClient
                self._client = MultiServerMCPClient(connections)
                self._tools = await self._client.get_tools()
                logger.info(f"Successfully loaded {len(self._tools)} MCP tool(s).")
            except ImportError:
                logger.warning(
                    "langchain-mcp-adapters not installed. "
                    "Install with: pip install langchain-mcp-adapters"
                )
                self._tools = []

        except Exception as e:
            logger.error(f"Failed to load MCP tools: {e}")
            self._tools = []

        self._loaded = True
        return self._tools or []

    async def close(self):
        """Close the MCP client connection."""
        if self._client is not None:
            try:
                await self._client.close()
            except Exception as e:
                logger.error(f"Error closing MCP client: {e}")
            self._client = None
            self._tools = None
            self._loaded = False


def get_mcp_browser_service() -> MCPBrowserService:
    """Get the global MCPBrowserService singleton."""
    global _mcp_service_instance
    if _mcp_service_instance is None:
        _mcp_service_instance = MCPBrowserService()
    return _mcp_service_instance
