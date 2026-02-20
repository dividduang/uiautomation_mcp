# -*- coding: utf-8 -*-
"""Query tools for getting control information."""

import logging
import os
import time
from typing import Optional, List

from mcp.server.fastmcp import FastMCP

import uiautomation as auto

from ..core import get_control_by_handle, format_error, check_admin
from ..config import config

logger = logging.getLogger(__name__)


def register_query_tools(mcp: FastMCP):
    """Register query tools with the MCP server."""

    @mcp.tool()
    def ui_get_properties(
        handle: int,
        properties: Optional[List[str]] = None,
    ) -> dict:
        """Get properties of a control.

        Args:
            handle: Control handle
            properties: Specific properties to get (default: all)
                Options: name, className, controlType, automationId, processId,
                         enabled, visible, rect, helpText, frameworkId

        Returns:
            Control properties
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
    def ui_get_text(handle: int) -> dict:
        """Get text content from a control.

        Args:
            handle: Control handle

        Returns:
            Text content
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
    def ui_get_rect(handle: int) -> dict:
        """Get bounding rectangle of a control.

        Args:
            handle: Control handle

        Returns:
            Rectangle coordinates
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
        handle: int,
        savePath: Optional[str] = None,
        captureCursor: bool = False,
    ) -> dict:
        """Take a screenshot of a control.

        Args:
            handle: Control handle
            savePath: Path to save screenshot (default: auto-generated)
            captureCursor: Whether to capture cursor

        Returns:
            Screenshot path
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
        handle: int,
        timeout: float = 0,
    ) -> dict:
        """Check if a control exists.

        Args:
            handle: Control handle
            timeout: Time to wait in seconds

        Returns:
            Whether control exists
        """
        check_admin()

        try:
            control = get_control_by_handle(handle)
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
        timeout: float = 10,
        parentHandle: Optional[int] = None,
    ) -> dict:
        """Wait for a condition to be met.

        Args:
            condition: Type of condition (control_exists, control_disappear, window_active)
            timeout: Timeout in seconds
            parentHandle: Parent control for condition check

        Returns:
            Whether condition was met
        """
        check_admin()

        try:
            start = time.time()

            while time.time() - start < timeout:
                if condition == "control_exists" and parentHandle:
                    control = get_control_by_handle(parentHandle)
                    if control and control.Exists():
                        return {"success": True, "data": {"met": True, "condition": condition}}

                elif condition == "control_disappear" and parentHandle:
                    control = get_control_by_handle(parentHandle)
                    if not control or not control.Exists():
                        return {"success": True, "data": {"met": True, "condition": condition}}

                elif condition == "window_active":
                    fg = auto.GetForegroundControl()
                    if parentHandle and fg and fg.NativeWindowHandle == parentHandle:
                        return {"success": True, "data": {"met": True, "condition": condition}}

                time.sleep(0.5)

            return {"success": True, "data": {"met": False, "condition": condition, "timeout": timeout}}

        except Exception as e:
            logger.exception("ui_wait_for failed")
            return format_error("INTERNAL_ERROR", str(e))
