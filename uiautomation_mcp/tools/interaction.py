# -*- coding: utf-8 -*-
"""Interaction operation tools."""

import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

import uiautomation as auto

from ..core import (
    get_control_by_handle,
    format_error,
    create_confirmation,
    confirm_operation,
    is_dangerous_tool,
    check_admin,
)
from ..config import config
from ..models import MouseButton

logger = logging.getLogger(__name__)

# Store pending confirmations for dangerous operations
_pending_confirms = {}


def register_interaction_tools(mcp: FastMCP):
    """Register interaction tools with the MCP server."""

    @mcp.tool()
    def ui_click(
        handle: Optional[int] = None,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = "left",
        double: bool = False,
    ) -> dict:
        """Click on a control or at coordinates.

        Args:
            handle: Control handle to click (uses center if no x/y)
            x: Relative X offset from control center, or absolute if no handle
            y: Relative Y offset from control center, or absolute if no handle
            button: Mouse button (left, right, middle)
            double: Whether to double-click

        Returns:
            Success or error
        """
        check_admin()

        try:
            # Click at absolute coordinates
            if handle is None and x is not None and y is not None:
                if button == "right":
                    auto.RightClick(x, y)
                elif button == "middle":
                    auto.MiddleClick(x, y)
                elif double:
                    auto.DoubleClick(x, y)
                else:
                    auto.Click(x, y)
                return {"success": True, "data": {"action": "click", "x": x, "y": y}}

            # Click on control
            control = get_control_by_handle(handle)
            if not control:
                return format_error(
                    "CONTROL_NOT_FOUND",
                    f"控件句柄无效: {handle}",
                )

            # Determine click method
            if button == "right":
                control.RightClick(x, y)
            elif button == "middle":
                control.MiddleClick(x, y)
            elif double:
                control.DoubleClick(x, y)
            else:
                control.Click(x, y)

            return {"success": True, "data": {"action": "click", "handle": handle}}

        except Exception as e:
            logger.exception("ui_click failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_send_keys(
        handle: int,
        text: str,
        interval: float = 0.05,
    ) -> dict:
        """Send keyboard input to a control.

        Args:
            handle: Control handle
            text: Text/keys to send (use {Ctrl}, {Enter}, etc. for special keys)
            interval: Interval between keystrokes in seconds

        Returns:
            Success or error
        """
        check_admin()

        try:
            control = get_control_by_handle(handle)
            if not control:
                return format_error(
                    "CONTROL_NOT_FOUND",
                    f"控件句柄无效: {handle}",
                )

            control.SendKeys(text, interval=interval)
            return {"success": True, "data": {"action": "send_keys", "text": text}}

        except Exception as e:
            logger.exception("ui_send_keys failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_set_value(
        handle: int,
        value: str,
    ) -> dict:
        """Set text value of a control using ValuePattern.

        Args:
            handle: Control handle
            value: Value to set

        Returns:
            Success or error
        """
        check_admin()

        try:
            control = get_control_by_handle(handle)
            if not control:
                return format_error(
                    "CONTROL_NOT_FOUND",
                    f"控件句柄无效: {handle}",
                )

            pattern = control.GetValuePattern()
            if not pattern:
                return format_error(
                    "PATTERN_NOT_SUPPORTED",
                    "控件不支持 ValuePattern",
                    ["尝试使用 ui_send_keys 发送键盘输入"],
                )

            pattern.SetValue(value)
            return {"success": True, "data": {"action": "set_value", "value": value}}

        except Exception as e:
            logger.exception("ui_set_value failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_close_window(
        handle: int,
        confirmationToken: Optional[str] = None,
    ) -> dict:
        """Close a window. Requires confirmation.

        Args:
            handle: Window handle
            confirmationToken: Token from previous confirmation (if required)

        Returns:
            Confirmation request, success, or error
        """
        check_admin()

        try:
            control = get_control_by_handle(handle)
            if not control:
                return format_error(
                    "CONTROL_NOT_FOUND",
                    f"窗口句柄无效: {handle}",
                )

            # Check if confirmation is needed
            if config.confirmation_enabled and not confirmationToken:
                request = create_confirmation(
                    "ui_close_window",
                    {"windowName": control.Name, "handle": handle},
                    f"即将关闭窗口「{control.Name}」，是否继续？",
                )
                return {"success": False, "requiresConfirmation": True, "confirmation": request.model_dump()}

            # Verify confirmation token
            if config.confirmation_enabled and confirmationToken:
                result = confirm_operation(confirmationToken, True)
                if not result:
                    return format_error("INVALID_CONFIRMATION", "确认令牌无效或已过期")

            # Close the window
            pattern = control.GetWindowPattern()
            if pattern:
                pattern.Close()
            else:
                # Fallback to Alt+F4
                control.SetFocus()
                auto.SendKeys("{Alt}{F4}")

            return {"success": True, "data": {"action": "close_window", "handle": handle}}

        except Exception as e:
            logger.exception("ui_close_window failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_move_window(
        handle: int,
        x: Optional[int] = None,
        y: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> dict:
        """Move and/or resize a window.

        Args:
            handle: Window handle
            x: New X position (optional)
            y: New Y position (optional)
            width: New width (optional)
            height: New height (optional)

        Returns:
            Success or error
        """
        check_admin()

        try:
            control = get_control_by_handle(handle)
            if not control:
                return format_error(
                    "CONTROL_NOT_FOUND",
                    f"窗口句柄无效: {handle}",
                )

            control.MoveWindow(x, y, width, height)
            return {
                "success": True,
                "data": {
                    "action": "move_window",
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                }
            }

        except Exception as e:
            logger.exception("ui_move_window failed")
            return format_error("INTERNAL_ERROR", str(e))
