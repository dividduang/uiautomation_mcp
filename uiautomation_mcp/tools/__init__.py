# -*- coding: utf-8 -*-
"""MCP tools for UIAutomation."""

from .discovery import register_discovery_tools
from .interaction import register_interaction_tools
from .query import register_query_tools
from .patterns import register_pattern_tools
from .helpers import register_helper_tools

__all__ = [
    "register_discovery_tools",
    "register_interaction_tools",
    "register_query_tools",
    "register_pattern_tools",
    "register_helper_tools",
]
