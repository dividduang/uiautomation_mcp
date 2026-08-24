# -*- coding: utf-8 -*-
"""Service layer — pure, MCP-free implementations of every UI operation.

These functions are the single source of truth behind both the CLI
(:mod:`uiautomation_mcp.cli`) and, historically, the MCP tools
(:mod:`uiautomation_mcp.tools`). They know nothing about FastMCP /
Model Context Protocol; they accept plain arguments and return plain
dicts shaped as ``{"success": True, "data": ...}`` or
``{"success": False, "error": {...}}``.

The one deliberate divergence from the old MCP tools: control *tokens*
are resolved through :mod:`uiautomation_mcp.registry`, which persists
them across processes (a CLI invocation is a fresh process each time).

Dangerous operations (``close_window``, ``terminate_process``) take a
``confirmed`` flag instead of an interactive confirmation round-trip;
the CLI is responsible for prompting the user / honouring ``--yes``.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

import uiautomation as auto
from uiautomation import ScrollAmount

from . import registry
from .config import config
from .core import (
    check_admin,
    control_to_info,
    find_control as core_find_control,
    format_error,
    format_success,
    get_control_by_handle,
)
from .models import ControlSelector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Control resolution helpers
# ---------------------------------------------------------------------------

def _get_control(token: Optional[str]) -> Optional[auto.Control]:
    """Resolve a token to a live control via the persistent registry."""
    if not token:
        return None
    return registry.get_control_by_token(token)


def _control_not_found(token: str) -> Dict[str, Any]:
    return format_error(
        "CONTROL_NOT_FOUND",
        f"控件 token 无效或已过期: {token}",
        ["使用 find-window / find-control 重新获取控件"],
    )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def find_window(
    name: Optional[str] = None,
    class_name: Optional[str] = None,
    process_id: Optional[int] = None,
    handle: Optional[int] = None,
) -> Dict[str, Any]:
    """Find a top-level window by name, class, process ID, or handle."""
    check_admin()
    try:
        if handle:
            control = auto.ControlFromHandle(handle)
        else:
            search_params: Dict[str, Any] = {"searchDepth": 1}
            if name:
                search_params["Name"] = name
            if class_name:
                search_params["ClassName"] = class_name
            if process_id:
                search_params["ProcessId"] = process_id
            control = auto.WindowControl(**search_params)

        if not control or not control.Exists():
            return format_error(
                "WINDOW_NOT_FOUND",
                f"未找到窗口: name={name}, className={class_name}, processId={process_id}",
                [
                    "使用 list-processes 查看运行中的进程",
                    "确认窗口已打开且可见",
                    "尝试部分名称匹配 (name-contains)",
                ],
            )

        token = registry.register_control(control)
        return format_success(control_to_info(control, token=token).model_dump())
    except Exception as e:
        logger.exception("find_window failed")
        return format_error("INTERNAL_ERROR", str(e))


def find_control(
    parent_handle: Optional[int] = None,
    control_type: Optional[str] = None,
    name: Optional[str] = None,
    name_contains: Optional[str] = None,
    name_regex: Optional[str] = None,
    class_name: Optional[str] = None,
    automation_id: Optional[str] = None,
    depth: int = 0xFFFFFFFF,
    index: int = 1,
) -> Dict[str, Any]:
    """Find a child control within a parent control."""
    check_admin()
    try:
        selector = ControlSelector(
            parent_handle=parent_handle,
            control_type=control_type,
            name=name,
            name_contains=name_contains,
            name_regex=name_regex,
            class_name=class_name,
            automation_id=automation_id,
            depth=depth,
            index=index,
        )
        control = core_find_control(selector)
        if not control or not control.Exists():
            return format_error(
                "CONTROL_NOT_FOUND",
                f"未找到控件: {selector.model_dump()}",
                [
                    "尝试使用 name-contains 进行模糊匹配",
                    "增加搜索深度 depth",
                    "使用 children 查看可用控件",
                ],
                {"searchParams": selector.model_dump()},
            )
        token = registry.register_control(control)
        return format_success(control_to_info(control, token=token).model_dump())
    except Exception as e:
        logger.exception("find_control failed")
        return format_error("INTERNAL_ERROR", str(e))


def get_children(token: str, depth: int = 1) -> Dict[str, Any]:
    """Get children of a control (depth = tree traversal depth, 1 = direct)."""
    check_admin()
    try:
        control = _get_control(token)
        if not control:
            return _control_not_found(token)

        children: List[Dict[str, Any]] = []

        def walk(ctrl: auto.Control, current_depth: int) -> None:
            if current_depth > depth:
                return
            for child in ctrl.GetChildren():
                tok = registry.register_control(child)
                children.append(control_to_info(child, token=tok).model_dump())
                walk(child, current_depth + 1)

        walk(control, 1)
        return format_success(children)
    except Exception as e:
        logger.exception("get_children failed")
        return format_error("INTERNAL_ERROR", str(e))


def get_focused() -> Dict[str, Any]:
    """Get the currently focused control."""
    check_admin()
    try:
        control = auto.GetFocusedControl()
        if not control:
            return format_error("NO_FOCUSED_CONTROL", "无法获取焦点控件")
        token = registry.register_control(control)
        return format_success(control_to_info(control, token=token).model_dump())
    except Exception as e:
        logger.exception("get_focused failed")
        return format_error("INTERNAL_ERROR", str(e))


def get_foreground() -> Dict[str, Any]:
    """Get the foreground window."""
    check_admin()
    try:
        control = auto.GetForegroundControl()
        if not control:
            return format_error("NO_FOREGROUND_WINDOW", "无法获取前台窗口")
        token = registry.register_control(control)
        return format_success(control_to_info(control, token=token).model_dump())
    except Exception as e:
        logger.exception("get_foreground failed")
        return format_error("INTERNAL_ERROR", str(e))


def control_from_point(x: int, y: int) -> Dict[str, Any]:
    """Get the control at screen coordinates."""
    check_admin()
    try:
        control = auto.ControlFromPoint(x, y)
        if not control:
            return format_error("NO_CONTROL_AT_POINT", f"坐标 ({x}, {y}) 处没有控件")
        token = registry.register_control(control)
        return format_success(control_to_info(control, token=token).model_dump())
    except Exception as e:
        logger.exception("control_from_point failed")
        return format_error("INTERNAL_ERROR", str(e))


# ---------------------------------------------------------------------------
# Interaction
# ---------------------------------------------------------------------------

def click(
    token: Optional[str] = None,
    x: Optional[int] = None,
    y: Optional[int] = None,
    button: str = "left",
    double: bool = False,
) -> Dict[str, Any]:
    """Click on a control or at absolute coordinates."""
    check_admin()
    try:
        if token is None and x is not None and y is not None:
            if button == "right" and double:
                auto.RightClick(x, y)
                auto.RightClick(x, y)
            elif button == "right":
                auto.RightClick(x, y)
            elif button == "middle":
                auto.MiddleClick(x, y)
            elif double:
                auto.DoubleClick(x, y)
            else:
                auto.Click(x, y)
            return format_success({"action": "click", "x": x, "y": y})

        control = _get_control(token)
        if not control:
            return _control_not_found(token or "")

        if button == "right" and double:
            control.RightClick(x, y)
            control.RightClick(x, y)
        elif button == "right":
            control.RightClick(x, y)
        elif button == "middle":
            control.MiddleClick(x, y)
        elif double:
            control.DoubleClick(x, y)
        else:
            control.Click(x, y)
        return format_success({"action": "click", "token": token})
    except Exception as e:
        logger.exception("click failed")
        return format_error("INTERNAL_ERROR", str(e))


def send_keys(token: str, text: str, interval: float = 0.05) -> Dict[str, Any]:
    """Send keyboard input to a control."""
    check_admin()
    try:
        control = _get_control(token)
        if not control:
            return _control_not_found(token)
        control.SendKeys(text, interval=interval)
        return format_success({"action": "send_keys", "text": text})
    except Exception as e:
        logger.exception("send_keys failed")
        return format_error("INTERNAL_ERROR", str(e))


def set_value(token: str, value: str) -> Dict[str, Any]:
    """Set text value of a control using ValuePattern."""
    check_admin()
    try:
        control = _get_control(token)
        if not control:
            return _control_not_found(token)
        pattern = control.GetValuePattern()
        if not pattern:
            return format_error(
                "PATTERN_NOT_SUPPORTED",
                "控件不支持 ValuePattern",
                ["尝试使用 send-keys 发送键盘输入"],
            )
        pattern.SetValue(value)
        return format_success({"action": "set_value", "value": value})
    except Exception as e:
        logger.exception("set_value failed")
        return format_error("INTERNAL_ERROR", str(e))


def close_window(token: str, confirmed: bool = False) -> Dict[str, Any]:
    """Close a window. ``confirmed`` must be True (the CLI prompts first)."""
    check_admin()
    try:
        control = _get_control(token)
        if not control:
            return _control_not_found(token)
        if config.confirmation_enabled and not confirmed:
            return format_error(
                "CONFIRMATION_REQUIRED",
                f"即将关闭窗口「{control.Name}」，需要确认 (使用 --yes 或交互确认)",
            )
        pattern = control.GetWindowPattern()
        if pattern:
            pattern.Close()
        else:
            control.SetFocus()
            auto.SendKeys("{Alt}{F4}")
        return format_success({"action": "close_window", "token": token})
    except Exception as e:
        logger.exception("close_window failed")
        return format_error("INTERNAL_ERROR", str(e))


def move_window(
    token: str,
    x: Optional[int] = None,
    y: Optional[int] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Dict[str, Any]:
    """Move and/or resize a window."""
    check_admin()
    try:
        control = _get_control(token)
        if not control:
            return _control_not_found(token)
        control.MoveWindow(x, y, width, height)
        return format_success({
            "action": "move_window",
            "x": x, "y": y, "width": width, "height": height,
        })
    except Exception as e:
        logger.exception("move_window failed")
        return format_error("INTERNAL_ERROR", str(e))


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

def invoke(token: str) -> Dict[str, Any]:
    """Invoke/click a control using InvokePattern."""
    check_admin()
    try:
        control = _get_control(token)
        if not control:
            return _control_not_found(token)
        pattern = control.GetInvokePattern()
        if not pattern:
            return format_error(
                "PATTERN_NOT_SUPPORTED",
                "控件不支持 InvokePattern",
                ["尝试使用 click 进行点击操作"],
            )
        pattern.Invoke()
        return format_success({"action": "invoke"})
    except Exception as e:
        logger.exception("invoke failed")
        return format_error("INTERNAL_ERROR", str(e))


def toggle(token: str) -> Dict[str, Any]:
    """Toggle a control state using TogglePattern."""
    check_admin()
    try:
        control = _get_control(token)
        if not control:
            return _control_not_found(token)
        pattern = control.GetTogglePattern()
        if not pattern:
            return format_error("PATTERN_NOT_SUPPORTED", "控件不支持 TogglePattern")
        pattern.Toggle()
        return format_success({"action": "toggle", "state": str(pattern.ToggleState)})
    except Exception as e:
        logger.exception("toggle failed")
        return format_error("INTERNAL_ERROR", str(e))


def expand_collapse(token: str, action: str = "expand") -> Dict[str, Any]:
    """Expand or collapse a control using ExpandCollapsePattern."""
    check_admin()
    try:
        control = _get_control(token)
        if not control:
            return _control_not_found(token)
        pattern = control.GetExpandCollapsePattern()
        if not pattern:
            return format_error("PATTERN_NOT_SUPPORTED", "控件不支持 ExpandCollapsePattern")
        if action == "expand":
            pattern.Expand()
        elif action == "collapse":
            pattern.Collapse()
        else:
            return format_error("INVALID_ACTION", f"无效操作: {action}", ["支持的操作: expand, collapse"])
        return format_success({"action": action})
    except Exception as e:
        logger.exception("expand_collapse failed")
        return format_error("INTERNAL_ERROR", str(e))


def select_item(token: str) -> Dict[str, Any]:
    """Select an item using SelectionItemPattern."""
    check_admin()
    try:
        control = _get_control(token)
        if not control:
            return _control_not_found(token)
        pattern = control.GetSelectionItemPattern()
        if not pattern:
            return format_error("PATTERN_NOT_SUPPORTED", "控件不支持 SelectionItemPattern")
        pattern.Select()
        return format_success({"action": "select", "isSelected": True})
    except Exception as e:
        logger.exception("select_item failed")
        return format_error("INTERNAL_ERROR", str(e))


def scroll(token: str, direction: str = "down", amount: str = "large") -> Dict[str, Any]:
    """Scroll a control using ScrollPattern (mouse-wheel fallback)."""
    check_admin()
    try:
        control = _get_control(token)
        if not control:
            return _control_not_found(token)
        pattern = control.GetScrollPattern()
        if not pattern:
            if direction in ("up", "down"):
                wheel_times = 3 if amount == "large" else 1
                if direction == "up":
                    control.WheelUp(wheelTimes=wheel_times)
                else:
                    control.WheelDown(wheelTimes=wheel_times)
                return format_success({"action": "scroll", "method": "wheel"})
            return format_error("PATTERN_NOT_SUPPORTED", "控件不支持 ScrollPattern")

        decrement = ScrollAmount.LargeDecrement if amount == "large" else ScrollAmount.SmallDecrement
        increment = ScrollAmount.LargeIncrement if amount == "large" else ScrollAmount.SmallIncrement

        if direction == "up":
            pattern.Scroll(ScrollAmount.NoAmount, decrement)
        elif direction == "down":
            pattern.Scroll(ScrollAmount.NoAmount, increment)
        elif direction == "left":
            pattern.Scroll(decrement, ScrollAmount.NoAmount)
        elif direction == "right":
            pattern.Scroll(increment, ScrollAmount.NoAmount)
        else:
            return format_error("INVALID_DIRECTION", f"无效方向: {direction}", ["支持的方向: up, down, left, right"])
        return format_success({"action": "scroll", "direction": direction})
    except Exception as e:
        logger.exception("scroll failed")
        return format_error("INTERNAL_ERROR", str(e))


def terminate_process(
    process_id: Optional[int] = None,
    process_name: Optional[str] = None,
    confirmed: bool = False,
) -> Dict[str, Any]:
    """Terminate a process. ``confirmed`` must be True (the CLI prompts first)."""
    check_admin()
    try:
        if config.confirmation_enabled and not confirmed:
            return format_error(
                "CONFIRMATION_REQUIRED",
                f"即将终止进程: {process_name or process_id}，需要确认 (使用 --yes 或交互确认)",
            )
        if process_id:
            success = auto.TerminateProcess(process_id)
        elif process_name:
            count = auto.TerminateProcessByName(process_name)
            success = count > 0
        else:
            return format_error("INVALID_PARAMS", "需要提供 process-id 或 process-name")
        return format_success({"terminated": success})
    except Exception as e:
        logger.exception("terminate_process failed")
        return format_error("INTERNAL_ERROR", str(e))


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

PROPERTY_KEYS = (
    "name", "className", "controlType", "automationId", "processId",
    "enabled", "visible", "helpText", "frameworkId", "handle", "rect",
)


def get_properties(token: str, properties: Optional[List[str]] = None) -> Dict[str, Any]:
    """Get properties of a control."""
    check_admin()
    try:
        control = _get_control(token)
        if not control:
            return _control_not_found(token)

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
                "left": rect.left, "top": rect.top,
                "right": rect.right, "bottom": rect.bottom,
                "width": rect.width(), "height": rect.height(),
            }
        except Exception:
            all_props["rect"] = None

        if properties:
            result = {k: v for k, v in all_props.items() if k in properties}
        else:
            result = all_props
        return format_success(result)
    except Exception as e:
        logger.exception("get_properties failed")
        return format_error("INTERNAL_ERROR", str(e))


def get_text(token: str) -> Dict[str, Any]:
    """Get text content from a control (ValuePattern → TextPattern → LegacyIAccessible → Name)."""
    check_admin()
    try:
        control = _get_control(token)
        if not control:
            return _control_not_found(token)
        try:
            pattern = control.GetValuePattern()
            if pattern:
                return format_success({"text": pattern.Value})
        except Exception:
            pass
        try:
            pattern = control.GetTextPattern()
            if pattern:
                return format_success({"text": pattern.DocumentRange.GetText(-1)})
        except Exception:
            pass
        try:
            pattern = control.GetLegacyIAccessiblePattern()
            if pattern:
                return format_success({"text": pattern.Value})
        except Exception:
            pass
        return format_success({"text": control.Name or ""})
    except Exception as e:
        logger.exception("get_text failed")
        return format_error("INTERNAL_ERROR", str(e))


def get_rect(token: str) -> Dict[str, Any]:
    """Get bounding rectangle of a control."""
    check_admin()
    try:
        control = _get_control(token)
        if not control:
            return _control_not_found(token)
        rect = control.BoundingRectangle
        return format_success({
            "left": rect.left, "top": rect.top,
            "right": rect.right, "bottom": rect.bottom,
            "width": rect.width(), "height": rect.height(),
            "centerX": rect.xcenter(), "centerY": rect.ycenter(),
        })
    except Exception as e:
        logger.exception("get_rect failed")
        return format_error("INTERNAL_ERROR", str(e))


def screenshot(
    token: str,
    save_path: Optional[str] = None,
    capture_cursor: bool = False,
) -> Dict[str, Any]:
    """Take a screenshot of a control."""
    check_admin()
    try:
        control = _get_control(token)
        if not control:
            return _control_not_found(token)
        if not save_path:
            os.makedirs(config.screenshot_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(config.screenshot_dir, f"screenshot_{timestamp}.png")
        control.CaptureToImage(save_path, captureCursor=capture_cursor)
        return format_success({"path": save_path})
    except Exception as e:
        logger.exception("screenshot failed")
        return format_error("INTERNAL_ERROR", str(e))


def exists(token: str, timeout: float = 0) -> Dict[str, Any]:
    """Check if a control exists."""
    check_admin()
    try:
        control = _get_control(token)
        if not control:
            return format_success({"exists": False})
        if timeout > 0:
            found = control.Exists(maxSearchSeconds=timeout)
        else:
            found = control.Exists()
        return format_success({"exists": found})
    except Exception as e:
        logger.exception("exists failed")
        return format_error("INTERNAL_ERROR", str(e))


def wait_for(
    condition: str,
    timeout: Optional[float] = None,
    token: Optional[str] = None,
    name: Optional[str] = None,
    class_name: Optional[str] = None,
    automation_id: Optional[str] = None,
    control_type: Optional[str] = None,
    depth: int = 0xFFFFFFFF,
) -> Dict[str, Any]:
    """Wait for a condition: control_exists | control_disappear | window_active."""
    check_admin()
    if timeout is None:
        timeout = config.default_timeout
    try:
        start = time.time()
        while time.time() - start < timeout:
            if condition in ("control_exists", "control_disappear"):
                if token:
                    control = _get_control(token)
                else:
                    selector = ControlSelector(
                        name=name, class_name=class_name,
                        automation_id=automation_id, control_type=control_type,
                        depth=depth,
                    )
                    control = core_find_control(selector)
                present = bool(control) and bool(control.Exists(0, 0))
                met = present if condition == "control_exists" else not present
                if met:
                    return format_success({"met": True, "condition": condition})
            elif condition == "window_active":
                if token:
                    control = _get_control(token)
                    if control:
                        fg = auto.GetForegroundControl()
                        if fg and fg.NativeWindowHandle == control.NativeWindowHandle:
                            return format_success({"met": True, "condition": condition})
            time.sleep(0.5)
        return format_success({"met": False, "condition": condition, "timeout": timeout})
    except Exception as e:
        logger.exception("wait_for failed")
        return format_error("INTERNAL_ERROR", str(e))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clipboard_get() -> Dict[str, Any]:
    """Get text from clipboard."""
    try:
        text = auto.GetClipboardText()
        return format_success({"text": text})
    except Exception as e:
        logger.exception("clipboard_get failed")
        return format_error("INTERNAL_ERROR", str(e))


def clipboard_set(text: str) -> Dict[str, Any]:
    """Set text to clipboard."""
    try:
        success = auto.SetClipboardText(text)
        return format_success({"text": text}) if success else format_error("CLIPBOARD_FAILED", "设置剪贴板失败")
    except Exception as e:
        logger.exception("clipboard_set failed")
        return format_error("INTERNAL_ERROR", str(e))


def _proc_attr(proc, *names, default=""):
    """Read an attribute from a ProcessInfo, tolerating field-name differences
    across uiautomation versions (Name/exeName, Id/pid, ExecutablePath/exePath)."""
    for n in names:
        if hasattr(proc, n):
            v = getattr(proc, n)
            if v is not None:
                return v
    return default


def list_processes(filter_: Optional[str] = None) -> Dict[str, Any]:
    """List running processes, optionally filtered by name (contains)."""
    try:
        processes = auto.GetProcesses(detailedInfo=True)
        result = []
        for proc in processes:
            name = str(_proc_attr(proc, "Name", "exeName"))
            if filter_ and filter_.lower() not in name.lower():
                continue
            result.append({
                "name": name,
                "pid": int(_proc_attr(proc, "Id", "pid", default=0)),
                "exePath": str(_proc_attr(proc, "ExecutablePath", "exePath")),
            })
        return format_success({"processes": result, "count": len(result)})
    except Exception as e:
        logger.exception("list_processes failed")
        return format_error("INTERNAL_ERROR", str(e))


def show_desktop() -> Dict[str, Any]:
    """Show desktop (minimize all windows)."""
    try:
        auto.ShowDesktop()
        return format_success({"action": "show_desktop"})
    except Exception as e:
        logger.exception("show_desktop failed")
        return format_error("INTERNAL_ERROR", str(e))


def get_screen_size() -> Dict[str, Any]:
    """Get screen size."""
    try:
        width, height = auto.GetScreenSize()
        return format_success({"width": width, "height": height})
    except Exception as e:
        logger.exception("get_screen_size failed")
        return format_error("INTERNAL_ERROR", str(e))


# ---------------------------------------------------------------------------
# Highlight
# ---------------------------------------------------------------------------

_COLOR_NAMES = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "orange": (255, 165, 0),
    "purple": (128, 0, 128),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "white": (255, 255, 255),
    "black": (0, 0, 0),
}


def _color_rgb(color: str) -> tuple:
    """Convert a color name or '#rrggbb' hex string to an (r, g, b) tuple."""
    c = color.strip().lower()
    if c in _COLOR_NAMES:
        return _COLOR_NAMES[c]
    if c.startswith("#") and len(c) == 7:
        try:
            return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
        except ValueError:
            pass
    raise ValueError(f"无法识别的颜色: {color!r} (支持颜色名或 #rrggbb)")


def highlight(
    token: Optional[str] = None,
    handle: Optional[int] = None,
    color: str = "red",
    thickness: int = 3,
    duration: float = 0.0,
    delay: float = 0.05,
) -> Dict[str, Any]:
    """Draw a colored outline around a control (token or handle)."""
    check_admin()
    try:
        control = None
        if token:
            control = _get_control(token)
        if control is None and handle:
            control = get_control_by_handle(handle)
        if control is None:
            return format_error(
                "CONTROL_NOT_FOUND",
                "无法解析控件 (token 或 handle 均无效)",
                ["使用 find-window / find-control 重新获取控件"],
            )
        try:
            import overlay_arrows_and_more as oaam
        except ImportError:
            return format_error(
                "DEPENDENCY_MISSING",
                "缺少 overlay-arrows-and-more 依赖，请执行: pip install overlay-arrows-and-more",
            )

        rgb = _color_rgb(color)
        rect = control.BoundingRectangle
        x, y = rect.left, rect.top
        width = rect.width()
        height = rect.height()

        # New API (>= 0.5): Overlay class.
        if hasattr(oaam, "Overlay"):
            from overlay_arrows_and_more import Brush

            overlay = oaam.Overlay(transparency=0.0)
            overlay.add(
                x=x, y=y, width=width, height=height,
                brush=Brush.solid, brush_color=rgb, thickness=thickness,
            )
            overlay.refresh()
            hold = duration if duration > 0 else 0.5  # one-shot flash: brief hold
            end = time.time() + hold
            while time.time() < end:
                overlay.refresh()
                time.sleep(delay)
            overlay.quit()
            return format_success({"status": "highlighted", "color": color, "thickness": thickness})

        # Legacy API (< 0.5): oaam.highlight.
        if hasattr(oaam, "highlight"):
            oaam.highlight(control, color=color, thickness=thickness)
            if duration > 0:
                end_time = time.time() + duration
                while time.time() < end_time:
                    oaam.highlight(control, color=color, thickness=thickness)
                    time.sleep(delay)
            return format_success({"status": "highlighted", "color": color, "thickness": thickness})

        return format_error(
            "UNSUPPORTED_API",
            "当前 overlay-arrows-and-more 版本没有可用的高亮 API",
        )
    except Exception as e:
        logger.exception("highlight failed")
        return format_error("HIGHLIGHT_ERROR", str(e))
