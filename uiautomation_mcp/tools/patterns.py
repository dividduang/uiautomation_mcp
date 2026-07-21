# -*- coding: utf-8 -*-
"""Pattern operation tools."""

import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

import uiautomation as auto
from uiautomation import ScrollAmount

from ..core import (
    get_control_by_token,
    format_error,
    create_confirmation,
    confirm_operation,
    check_admin,
)
from ..config import config

logger = logging.getLogger(__name__)


def register_pattern_tools(mcp: FastMCP):
    """Register pattern tools with the MCP server."""

    @mcp.tool()
    def ui_invoke(token: str) -> dict:
        """Invoke/click a control using InvokePattern.

        Args:
            token: Control token from find tools

        Returns:
            Success or error
        """
        check_admin()

        try:
            control = get_control_by_token(token)
            if not control:
                return format_error(
                    "CONTROL_NOT_FOUND",
                    f"控件 token 无效或已过期: {token}",
                    ["使用 find 工具重新获取控件"]
                )

            pattern = control.GetInvokePattern()
            if not pattern:
                return format_error(
                    "PATTERN_NOT_SUPPORTED",
                    "控件不支持 InvokePattern",
                    ["尝试使用 ui_click 进行点击操作"],
                )

            pattern.Invoke()
            return {"success": True, "data": {"action": "invoke"}}

        except Exception as e:
            logger.exception("ui_invoke failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_toggle(token: str) -> dict:
        """Toggle a control state using TogglePattern.

        Args:
            token: Control token from find tools

        Returns:
            New toggle state or error
        """
        check_admin()

        try:
            control = get_control_by_token(token)
            if not control:
                return format_error(
                    "CONTROL_NOT_FOUND",
                    f"控件 token 无效或已过期: {token}",
                    ["使用 find 工具重新获取控件"]
                )

            pattern = control.GetTogglePattern()
            if not pattern:
                return format_error(
                    "PATTERN_NOT_SUPPORTED",
                    "控件不支持 TogglePattern",
                )

            pattern.Toggle()
            return {"success": True, "data": {"action": "toggle", "state": str(pattern.ToggleState)}}

        except Exception as e:
            logger.exception("ui_toggle failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_expand_collapse(
        token: str,
        action: str = "expand",
    ) -> dict:
        """Expand or collapse a control using ExpandCollapsePattern.

        Args:
            token: Control token from find tools
            action: Action to perform (expand, collapse)

        Returns:
            Success or error
        """
        check_admin()

        try:
            control = get_control_by_token(token)
            if not control:
                return format_error(
                    "CONTROL_NOT_FOUND",
                    f"控件 token 无效或已过期: {token}",
                    ["使用 find 工具重新获取控件"]
                )

            pattern = control.GetExpandCollapsePattern()
            if not pattern:
                return format_error(
                    "PATTERN_NOT_SUPPORTED",
                    "控件不支持 ExpandCollapsePattern",
                )

            if action == "expand":
                pattern.Expand()
            elif action == "collapse":
                pattern.Collapse()
            else:
                return format_error(
                    "INVALID_ACTION",
                    f"无效操作: {action}",
                    ["支持的操作: expand, collapse"],
                )

            return {"success": True, "data": {"action": action}}

        except Exception as e:
            logger.exception("ui_expand_collapse failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_select_item(token: str) -> dict:
        """Select an item using SelectionItemPattern.

        Args:
            token: Control token from find tools

        Returns:
            Success or error
        """
        check_admin()

        try:
            control = get_control_by_token(token)
            if not control:
                return format_error(
                    "CONTROL_NOT_FOUND",
                    f"控件 token 无效或已过期: {token}",
                    ["使用 find 工具重新获取控件"]
                )

            pattern = control.GetSelectionItemPattern()
            if not pattern:
                return format_error(
                    "PATTERN_NOT_SUPPORTED",
                    "控件不支持 SelectionItemPattern",
                )

            pattern.Select()
            return {"success": True, "data": {"action": "select", "isSelected": True}}

        except Exception as e:
            logger.exception("ui_select_item failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_scroll(
        token: str,
        direction: str = "down",
        amount: str = "large",
    ) -> dict:
        """Scroll a control using ScrollPattern.

        Args:
            token: Control token from find tools
            direction: Scroll direction (up, down, left, right)
            amount: Scroll amount (large, small)

        Returns:
            Success or error
        """
        check_admin()

        try:
            control = get_control_by_token(token)
            if not control:
                return format_error(
                    "CONTROL_NOT_FOUND",
                    f"控件 token 无效或已过期: {token}",
                    ["使用 find 工具重新获取控件"]
                )

            pattern = control.GetScrollPattern()
            if not pattern:
                # Try mouse wheel as fallback
                if direction in ("up", "down"):
                    wheel_times = 3 if amount == "large" else 1
                    if direction == "up":
                        control.WheelUp(wheelTimes=wheel_times)
                    else:
                        control.WheelDown(wheelTimes=wheel_times)
                    return {"success": True, "data": {"action": "scroll", "method": "wheel"}}
                return format_error(
                    "PATTERN_NOT_SUPPORTED",
                    "控件不支持 ScrollPattern",
                )

            # Map direction and amount to ScrollAmount
            # Decrement = scroll up/left (0 or 1), Increment = scroll down/right (3 or 4)
            decrement = ScrollAmount.LargeDecrement if amount == "large" else ScrollAmount.SmallDecrement
            increment = ScrollAmount.LargeIncrement if amount == "large" else ScrollAmount.SmallIncrement

            # Scroll(horizontalAmount, verticalAmount): vertical is the 2nd param,
            # horizontal is the 1st param. up/down -> vertical, left/right -> horizontal.
            if direction == "up":
                pattern.Scroll(ScrollAmount.NoAmount, decrement)
            elif direction == "down":
                pattern.Scroll(ScrollAmount.NoAmount, increment)
            elif direction == "left":
                pattern.Scroll(decrement, ScrollAmount.NoAmount)
            elif direction == "right":
                pattern.Scroll(increment, ScrollAmount.NoAmount)
            else:
                return format_error(
                    "INVALID_DIRECTION",
                    f"无效方向: {direction}",
                    ["支持的方向: up, down, left, right"],
                )

            return {"success": True, "data": {"action": "scroll", "direction": direction}}

        except Exception as e:
            logger.exception("ui_scroll failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_terminate_process(
        processId: Optional[int] = None,
        processName: Optional[str] = None,
        confirmationToken: Optional[str] = None,
    ) -> dict:
        """Terminate a process. Requires confirmation.

        Args:
            processId: Process ID to terminate
            processName: Process name to terminate (alternative to processId)
            confirmationToken: Token from previous confirmation

        Returns:
            Confirmation request, success, or error
        """
        check_admin()

        try:
            # Check confirmation
            if config.confirmation_enabled and not confirmationToken:
                request = create_confirmation(
                    "ui_terminate_process",
                    {"processId": processId, "processName": processName},
                    f"即将终止进程: {processName or processId}，是否继续？",
                )
                return {"success": False, "requiresConfirmation": True, "confirmation": request.model_dump()}

            if config.confirmation_enabled and confirmationToken:
                result = confirm_operation(confirmationToken, True)
                if not result:
                    return format_error("INVALID_CONFIRMATION", "确认令牌无效或已过期")

            # Terminate process
            if processId:
                success = auto.TerminateProcess(processId)
            elif processName:
                count = auto.TerminateProcessByName(processName)
                success = count > 0
            else:
                return format_error(
                    "INVALID_PARAMS",
                    "需要提供 processId 或 processName",
                )

            return {"success": True, "data": {"terminated": success}}

        except Exception as e:
            logger.exception("ui_terminate_process failed")
            return format_error("INTERNAL_ERROR", str(e))
