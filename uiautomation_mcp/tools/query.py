# -*- coding: utf-8 -*-
"""Query tools for getting control information."""

import logging
import os
import time
from typing import Optional, List

from mcp.server.fastmcp import FastMCP

import uiautomation as auto

from ..core import (
    get_control_by_token,
    find_control,
    format_error,
    check_admin,
)
from ..config import config
from ..models import ControlSelector

logger = logging.getLogger(__name__)


def register_query_tools(mcp: FastMCP):
    """Register query tools with the MCP server."""

    @mcp.tool()
    def ui_get_properties(
        token: str,
        properties: Optional[List[str]] = None,
    ) -> dict:
        """Get properties of a control.

        Args:
            token: Control token from find tools
            properties: Specific properties to get (default: all)
                Options: name, className, controlType, automationId, processId,
                         enabled, visible, rect, helpText, frameworkId

        Returns:
            Control properties
        """
        check_admin()

        try:
            control = get_control_by_token(token)
            if not control:
                return format_error(
                    "CONTROL_NOT_FOUND",
                    f"控件 token 无效或已过期: {token}",
                    ["使用 find 工具重新获取控件"],
                )

            all_props = {
                "name": control.Name,
                "className": control.ClassName,
                "controlType": control.ControlTypeName,
                "automationId": control.AutomationId,
                "processId": control.ProcessId,
                "enabled": control.IsEnabled,
                "visible": not control.IsOffscreen,
                "helpText": control.HelpText,
                "frameworkId": control.FrameworkId,
                "handle": control.NativeWindowHandle,
            }

            try:
                rect = control.BoundingRectangle
                all_props["rect"] = {
                    "left": rect.left,
                    "top": rect.top,
                    "right": rect.right,
                    "bottom": rect.bottom,
                    "width": rect.width(),
                    "height": rect.height(),
                }
            except Exception:
                all_props["rect"] = None

            if properties:
                result = {k: v for k, v in all_props.items() if k in properties}
            else:
                result = all_props

            return {"success": True, "data": result}

        except Exception as e:
            logger.exception("ui_get_properties failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_get_text(token: str) -> dict:
        """Get text content from a control.

        Args:
            token: Control token from find tools

        Returns:
            Text content
        """
        check_admin()

        try:
            control = get_control_by_token(token)
            if not control:
                return format_error(
                    "CONTROL_NOT_FOUND",
                    f"控件 token 无效或已过期: {token}",
                    ["使用 find 工具重新获取控件"],
                )

            # Try ValuePattern first
            try:
                pattern = control.GetValuePattern()
                if pattern:
                    return {"success": True, "data": {"text": pattern.Value}}
            except Exception:
                pass

            # Try TextPattern
            try:
                pattern = control.GetTextPattern()
                if pattern:
                    return {"success": True, "data": {"text": pattern.DocumentRange.GetText(-1)}}
            except Exception:
                pass

            # Try LegacyIAccessiblePattern
            try:
                pattern = control.GetLegacyIAccessiblePattern()
                if pattern:
                    return {"success": True, "data": {"text": pattern.Value}}
            except Exception:
                pass

            # Fallback to Name property
            return {"success": True, "data": {"text": control.Name or ""}}

        except Exception as e:
            logger.exception("ui_get_text failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_get_rect(token: str) -> dict:
        """Get bounding rectangle of a control.

        Args:
            token: Control token from find tools

        Returns:
            Rectangle coordinates
        """
        check_admin()

        try:
            control = get_control_by_token(token)
            if not control:
                return format_error(
                    "CONTROL_NOT_FOUND",
                    f"控件 token 无效或已过期: {token}",
                    ["使用 find 工具重新获取控件"],
                )

            rect = control.BoundingRectangle
            return {
                "success": True,
                "data": {
                    "left": rect.left,
                    "top": rect.top,
                    "right": rect.right,
                    "bottom": rect.bottom,
                    "width": rect.width(),
                    "height": rect.height(),
                    "centerX": rect.xcenter(),
                    "centerY": rect.ycenter(),
                }
            }

        except Exception as e:
            logger.exception("ui_get_rect failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_screenshot(
        token: str,
        savePath: Optional[str] = None,
        captureCursor: bool = False,
    ) -> dict:
        """Take a screenshot of a control.

        Args:
            token: Control token from find tools
            savePath: Path to save screenshot (default: auto-generated)
            captureCursor: Whether to capture cursor

        Returns:
            Screenshot path
        """
        check_admin()

        try:
            control = get_control_by_token(token)
            if not control:
                return format_error(
                    "CONTROL_NOT_FOUND",
                    f"控件 token 无效或已过期: {token}",
                    ["使用 find 工具重新获取控件"],
                )

            # Generate default path
            if not savePath:
                os.makedirs(config.screenshot_dir, exist_ok=True)
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                savePath = os.path.join(config.screenshot_dir, f"screenshot_{timestamp}.png")

            control.CaptureToImage(savePath, captureCursor=captureCursor)
            return {"success": True, "data": {"path": savePath}}

        except Exception as e:
            logger.exception("ui_screenshot failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_exists(
        token: str,
        timeout: float = 0,
    ) -> dict:
        """Check if a control exists.

        Args:
            token: Control token (from find tools)
            timeout: Time to wait in seconds

        Returns:
            Whether control exists
        """
        check_admin()

        try:
            control = get_control_by_token(token)
            if not control:
                return {"success": True, "data": {"exists": False}}

            if timeout > 0:
                exists = control.Exists(maxSearchSeconds=timeout)
            else:
                exists = control.Exists()

            return {"success": True, "data": {"exists": exists}}

        except Exception as e:
            logger.exception("ui_exists failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_wait_for(
        condition: str,
        timeout: Optional[float] = None,
        token: Optional[str] = None,
        name: Optional[str] = None,
        className: Optional[str] = None,
        automationId: Optional[str] = None,
        controlType: Optional[str] = None,
        depth: int = 0xFFFFFFFF,
    ) -> dict:
        """Wait for a condition to be met.

        Args:
            condition: Type of condition (control_exists, control_disappear, window_active)
            timeout: Timeout in seconds (uses config.default_timeout if None)
            token: Control token to wait for (for control_exists/control_disappear)
            name: Control name selector (for control_exists)
            className: Windows class name selector (for control_exists)
            automationId: Automation ID selector (for control_exists)
            controlType: Control type selector (for control_exists)
            depth: Search depth for control_exists

        Returns:
            Whether condition was met
        """
        check_admin()

        # Use default timeout if not provided
        if timeout is None:
            timeout = config.default_timeout

        try:
            start = time.time()

            while time.time() - start < timeout:
                if condition == "control_exists":
                    # Try to find control using token or selector parameters
                    if token:
                        control = get_control_by_token(token)
                    else:
                        # Build selector from parameters
                        selector = ControlSelector(
                            name=name,
                            class_name=className,
                            automation_id=automationId,
                            control_type=controlType,
                            depth=depth,
                        )
                        control = find_control(selector)

                    if control and control.Exists(0, 0):
                        return {"success": True, "data": {"met": True, "condition": condition}}

                elif condition == "control_disappear":
                    # Check if control has disappeared
                    if token:
                        control = get_control_by_token(token)
                    else:
                        selector = ControlSelector(
                            name=name,
                            class_name=className,
                            automation_id=automationId,
                            control_type=controlType,
                            depth=depth,
                        )
                        control = find_control(selector)

                    if not control or not control.Exists(0, 0):
                        return {"success": True, "data": {"met": True, "condition": condition}}

                elif condition == "window_active":
                    # Wait for window to become active (requires token to check)
                    if token:
                        control = get_control_by_token(token)
                        if control:
                            fg = auto.GetForegroundControl()
                            if fg and fg.NativeWindowHandle == control.NativeWindowHandle:
                                return {"success": True, "data": {"met": True, "condition": condition}}

                time.sleep(0.5)

            return {"success": True, "data": {"met": False, "condition": condition, "timeout": timeout}}

        except Exception as e:
            logger.exception("ui_wait_for failed")
            return format_error("INTERNAL_ERROR", str(e))
