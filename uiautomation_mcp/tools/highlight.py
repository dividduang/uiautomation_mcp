# -*- coding: utf-8 -*-
"""Highlight tools for drawing outlines and borders around controls."""

import logging
import time
import overlay_arrows_and_more as oaam
from typing import Optional, Dict, Any, Union

from mcp.server.fastmcp import FastMCP

import uiautomation as auto

from ..core import get_control_by_handle, format_error, check_admin
from ..config import config

logger = logging.getLogger(__name__)


def _draw_outline(
    control: auto.Control,
    color: str = "red",
    thickness: int = 3,
    duration: float = 0.0,
    delay: float = 0.05,
) -> Dict[str, Any]:
    """Core function to draw outline using overlay_arrows_and_more.

    Args:
        control: The control to highlight
        color: Color name or hex code (e.g. 'red', '#00ff00', 'blue')
        thickness: Border thickness in pixels
        duration: Duration in seconds to keep highlight visible (0 = one-time flash)
        delay: Sleep time between updates (for persistent highlight)

    Returns:
        Status dictionary
    """
    try:
        # 使用 overlay_arrows_and_more 进行高亮
        oaam.highlight(control, color=color, thickness=thickness)

        # 持续高亮模式
        if duration > 0:
            end_time = time.time() + duration
            while time.time() < end_time:
                oaam.highlight(control, color=color, thickness=thickness)
                time.sleep(delay)

        return {"success": True, "data": {"status": "highlighted", "color": color, "thickness": thickness}}
    except Exception as e:
        logger.exception("highlight failed")
        return format_error("HIGHLIGHT_ERROR", str(e))


def register_highlight_tools(mcp: FastMCP):
    """Register highlight tools with the MCP server."""

    @mcp.tool()
    def ui_highlight(
        handle: int,
        color: str = "red",
        thickness: int = 3,
        duration: float = 0.0,
        delay: float = 0.05,
    ) -> Dict[str, Any]:
        """Draw a colored outline around a control.

        Args:
            handle: Control handle (from ui_find_control)
            color: Color name or hex code (e.g. 'red', '#00ff00', 'blue')
            thickness: Border thickness in pixels
            duration: Duration in seconds to keep highlight visible (0 = one-time)
            delay: Sleep time between updates (for persistent highlight)

        Returns:
            Status of the highlight operation
        """
        check_admin()

        try:
            control = get_control_by_handle(handle)
            if not control:
                return format_error(
                    "CONTROL_NOT_FOUND",
                    f"控件句柄无效: {handle}",
                    ["句柄可能已过期，请重新查找控件"],
                )

            return _draw_outline(control, color, thickness, duration, delay)

        except Exception as e:
            logger.exception("ui_highlight failed")
            return format_error("INTERNAL_ERROR", str(e))


def register_all_tools(mcp: FastMCP):
    """Register all highlight-related tools."""
    register_highlight_tools(mcp)

    # Also expose the core function for direct Python use
    mcp.add_tool("highlight_control", _draw_outline, {"description": "Core highlight function for Python use"})