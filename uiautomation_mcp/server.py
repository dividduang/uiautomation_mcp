# -*- coding: utf-8 -*-
"""UIAutomation MCP Server entry point."""

import logging
from mcp.server.fastmcp import FastMCP

from . import __version__
from .config import config
from .tools import (
    register_discovery_tools,
    register_interaction_tools,
    register_query_tools,
    register_pattern_tools,
    register_helper_tools,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP(
    name="UIAutomation",
    instructions=f"Windows UI Automation MCP Server v{__version__} - Provides tools for discovering, querying, and interacting with Windows UI controls.",
)

# Register all tools
register_discovery_tools(mcp)
register_interaction_tools(mcp)
register_query_tools(mcp)
register_pattern_tools(mcp)
register_helper_tools(mcp)


def main():
    """Main entry point for the MCP server."""
    logger.info(f"Starting UIAutomation MCP Server v{__version__}")
    logger.info(f"Configuration: timeout={config.default_timeout}s, admin_check={config.admin_check}")
    mcp.run()


if __name__ == "__main__":
    main()
