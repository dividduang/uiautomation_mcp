# -*- coding: utf-8 -*-
"""Control discovery tools."""

import logging
from typing import Optional, List

from mcp.server.fastmcp import FastMCP

import uiautomation as auto

from ..core import (
    control_to_info,
    find_control,
    register_control,
    get_control_by_token,
    format_error,
    check_admin,
)
from ..models import ControlSelector, ControlInfo

logger = logging.getLogger(__name__)


def register_discovery_tools(mcp: FastMCP):
    """Register discovery tools with the MCP server."""

    @mcp.tool()
    def ui_find_window(
        name: Optional[str] = None,
        className: Optional[str] = None,
        processId: Optional[int] = None,
        handle: Optional[int] = None,
    ) -> dict:
        """Find a top-level window by name, class, process ID, or handle.

        Args:
            name: Window title (exact match)
            className: Windows class name
            processId: Process ID
            handle: Window handle (returns directly if provided)

        Returns:
            Window control info or error
        """
        check_admin()

        try:
            if handle:
                control = auto.ControlFromHandle(handle)
            else:
                search_params = {"searchDepth": 1}
                if name:
                    search_params["Name"] = name
                if className:
                    search_params["ClassName"] = className
                if processId:
                    search_params["ProcessId"] = processId
                control = auto.WindowControl(**search_params)

            if not control or not control.Exists():
                return format_error(
                    "WINDOW_NOT_FOUND",
                    f"未找到窗口: name={name}, className={className}, processId={processId}",
                    [
                        "使用 ui_list_processes 查看运行中的进程",
                        "确认窗口已打开且可见",
                        "尝试部分名称匹配",
                    ]
                )

            token = register_control(control)
            return {"success": True, "data": control_to_info(control, token=token).model_dump()}

        except Exception as e:
            logger.exception("ui_find_window failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_find_control(
        parentHandle: Optional[int] = None,
        controlType: Optional[str] = None,
        name: Optional[str] = None,
        nameContains: Optional[str] = None,
        nameRegex: Optional[str] = None,
        className: Optional[str] = None,
        automationId: Optional[str] = None,
        depth: int = 0xFFFFFFFF,
        index: int = 1,
    ) -> dict:
        """Find a child control within a parent control.

        Args:
            parentHandle: Parent control handle (searches from root if not provided)
            controlType: Control type (e.g., ButtonControl, EditControl)
            name: Exact name match
            nameContains: Name contains this string
            nameRegex: Regex pattern for name
            className: Windows class name
            automationId: Automation ID
            depth: Search depth (default unlimited)
            index: Nth matching control (1-based)

        Returns:
            Control info or error
        """
        check_admin()

        try:
            selector = ControlSelector(
                parent_handle=parentHandle,
                control_type=controlType,
                name=name,
                name_contains=nameContains,
                name_regex=nameRegex,
                class_name=className,
                automation_id=automationId,
                depth=depth,
                index=index,
            )

            control = find_control(selector)

            if not control or not control.Exists():
                return format_error(
                    "CONTROL_NOT_FOUND",
                    f"未找到控件: {selector.model_dump()}",
                    [
                        "尝试使用 nameContains 进行模糊匹配",
                        "增加搜索深度 depth",
                        "使用 ui_get_children 查看可用控件",
                    ],
                    {"searchParams": selector.model_dump()},
                )

            token = register_control(control)
            return {"success": True, "data": control_to_info(control, token=token).model_dump()}

        except Exception as e:
            logger.exception("ui_find_control failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_get_children(
        token: str,
        depth: int = 1,
    ) -> dict:
        """Get children of a control.

        Args:
            token: Parent control token (from find tools)
            depth: Depth to traverse (default 1 = direct children only)

        Returns:
            List of child controls
        """
        check_admin()

        try:
            control = get_control_by_token(token)
            if not control:
                return format_error(
                    "CONTROL_NOT_FOUND",
                    f"控件 token 无效或已过期: {token}",
                    ["token 可能已过期，请重新查找控件"],
                )

            children = []

            def walk(ctrl: auto.Control, current_depth: int):
                if current_depth > depth:
                    return
                for child in ctrl.GetChildren():
                    token = register_control(child)
                    children.append(control_to_info(child, token=token).model_dump())
                    walk(child, current_depth + 1)

            walk(control, 1)
            return {"success": True, "data": children}

        except Exception as e:
            logger.exception("ui_get_children failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_get_focused() -> dict:
        """Get the currently focused control.

        Returns:
            Focused control info
        """
        check_admin()

        try:
            control = auto.GetFocusedControl()
            if not control:
                return format_error("NO_FOCUSED_CONTROL", "无法获取焦点控件")

            token = register_control(control)
            return {"success": True, "data": control_to_info(control, token=token).model_dump()}

        except Exception as e:
            logger.exception("ui_get_focused failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_get_foreground() -> dict:
        """Get the foreground window.

        Returns:
            Foreground window info
        """
        check_admin()

        try:
            control = auto.GetForegroundControl()
            if not control:
                return format_error("NO_FOREGROUND_WINDOW", "无法获取前台窗口")

            token = register_control(control)
            return {"success": True, "data": control_to_info(control, token=token).model_dump()}

        except Exception as e:
            logger.exception("ui_get_foreground failed")
            return format_error("INTERNAL_ERROR", str(e))

    @mcp.tool()
    def ui_control_from_point(
        x: int,
        y: int,
    ) -> dict:
        """Get the control at screen coordinates.

        Args:
            x: Screen X coordinate
            y: Screen Y coordinate

        Returns:
            Control info at the point
        """
        check_admin()

        try:
            control = auto.ControlFromPoint(x, y)
            if not control:
                return format_error(
                    "NO_CONTROL_AT_POINT",
                    f"坐标 ({x}, {y}) 处没有控件",
                )

            token = register_control(control)
            return {"success": True, "data": control_to_info(control, token=token).model_dump()}

        except Exception as e:
            logger.exception("ui_control_from_point failed")
            return format_error("INTERNAL_ERROR", str(e))
