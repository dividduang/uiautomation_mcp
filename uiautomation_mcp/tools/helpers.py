# -*- coding: utf-8 -*-
"""Helper tools for common operations."""

import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

import uiautomation as auto

from ..core import format_error

logger = logging.getLogger(__name__)


def register_helper_tools(mcp: FastMCP):
    """Register helper tools with the MCP server."""

    @mcp.tool()
    def ui_clipboard_get() -> dict:
        """Get text from clipboard.

        Returns:
            Clipboard text content
        """
        try:
            text = auto.GetClipboardText()
            return {"success": True, "data": {"text": text}}

        except Exception as e:
            logger.exception("ui_clipboard_get failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_clipboard_set(text: str) -> dict:
        """Set text to clipboard.

        Args:
            text: Text to set

        Returns:
            Success or error
        """
        try:
            success = auto.SetClipboardText(text)
            return {"success": success, "data": {"text": text}}

        except Exception as e:
            logger.exception("ui_clipboard_set failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_list_processes(filter: Optional[str] = None) -> dict:
        """List running processes.

        Args:
            filter: Filter process name (contains)

        Returns:
            List of processes
        """
        try:
            processes = auto.GetProcesses(detailedInfo=True)
            result = []

            for proc in processes:
                if filter and filter.lower() not in proc.Name.lower():
                    continue
                result.append({
                    "name": proc.Name,
                    "pid": proc.Id,
                    "exePath": proc.ExecutablePath or "",
                })

            return {"success": True, "data": {"processes": result, "count": len(result)}}

        except Exception as e:
            logger.exception("ui_list_processes failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_show_desktop() -> dict:
        """Show desktop (minimize all windows).

        Returns:
            Success
        """
        try:
            auto.ShowDesktop()
            return {"success": True, "data": {"action": "show_desktop"}}

        except Exception as e:
            logger.exception("ui_show_desktop failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_get_screen_size() -> dict:
        """Get screen size.

        Returns:
            Screen width and height
        """
        try:
            width, height = auto.GetScreenSize()
            return {"success": True, "data": {"width": width, "height": height}}

        except Exception as e:
            logger.exception("ui_get_screen_size failed")
            return format_error("INTERNAL_ERROR", str(e))
