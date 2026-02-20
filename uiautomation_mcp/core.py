# -*- coding: utf-8 -*-
"""Core wrapper for UIAutomation operations."""

import ctypes
import logging
import uuid
from typing import Optional, Any, Dict, List

import uiautomation as auto

from .config import config
from .models import ControlInfo, ControlSelector, ConfirmationRequest

logger = logging.getLogger(__name__)


def is_admin() -> bool:
    """Check if running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def check_admin() -> None:
    """Check admin privileges and warn if not available."""
    if config.admin_check and not is_admin():
        logger.warning(
            "Not running as administrator. Some operations may fail. "
            "Consider running with admin privileges."
        )


# Pending confirmations storage
_pending_confirmations: Dict[str, ConfirmationRequest] = {}


def create_confirmation(tool: str, details: Dict[str, Any], message: str) -> ConfirmationRequest:
    """Create a confirmation request for a dangerous operation.

    Args:
        tool: Name of the tool requesting confirmation.
        details: Details about the operation (e.g., window handle, process ID).
        message: Human-readable message explaining the operation.

    Returns:
        ConfirmationRequest with a unique token for tracking.
    """
    token = str(uuid.uuid4())[:8]
    request = ConfirmationRequest(
        tool=tool,
        details=details,
        message=message,
        confirmation_token=token,
    )
    _pending_confirmations[token] = request
    return request


def confirm_operation(token: str, approved: bool) -> Optional[ConfirmationRequest]:
    """Confirm or reject a pending operation.

    Args:
        token: The confirmation token from the original request.
        approved: Whether the operation was approved.

    Returns:
        The original ConfirmationRequest if approved, None otherwise.
    """
    request = _pending_confirmations.pop(token, None)
    if request and approved:
        return request
    return None


def get_pending_confirmation(token: str) -> Optional[ConfirmationRequest]:
    """Get a pending confirmation without removing it.

    Args:
        token: The confirmation token to look up.

    Returns:
        The ConfirmationRequest if found, None otherwise.
    """
    return _pending_confirmations.get(token)


def clear_pending_confirmations() -> None:
    """Clear all pending confirmations."""
    _pending_confirmations.clear()


def is_dangerous_tool(tool_name: str) -> bool:
    """Check if a tool requires confirmation.

    Args:
        tool_name: Name of the tool to check.

    Returns:
        True if the tool is considered dangerous and requires confirmation.
    """
    return tool_name in ["ui_close_window", "ui_terminate_process"]


def control_to_info(control: auto.Control) -> ControlInfo:
    """Convert a Control object to ControlInfo model.

    Args:
        control: The uiautomation Control object.

    Returns:
        ControlInfo with extracted properties.
    """
    try:
        rect = control.BoundingRectangle
        rect_dict = {
            "left": rect.left,
            "top": rect.top,
            "right": rect.right,
            "bottom": rect.bottom,
        } if rect else None
    except Exception:
        rect_dict = None

    return ControlInfo(
        handle=control.NativeWindowHandle or 0,
        name=control.Name or "",
        class_name=control.ClassName or "",
        control_type=control.ControlTypeName or "",
        automation_id=control.AutomationId or "",
        process_id=control.ProcessId or 0,
        enabled=control.IsEnabled if control.IsEnabled is not None else True,
        visible=not control.IsOffscreen if control.IsOffscreen is not None else True,
        rect=rect_dict,
    )


def find_control(selector: ControlSelector) -> Optional[auto.Control]:
    """Find a control using selector parameters.

    Args:
        selector: ControlSelector with search criteria.

    Returns:
        Found Control object or None if not found.
    """
    # Build search parameters
    search_params: Dict[str, Any] = {}
    if selector.name:
        search_params["Name"] = selector.name
    if selector.name_contains:
        search_params["SubName"] = selector.name_contains
    if selector.name_regex:
        search_params["RegexName"] = selector.name_regex
    if selector.class_name:
        search_params["ClassName"] = selector.class_name
    if selector.automation_id:
        search_params["AutomationId"] = selector.automation_id
    if selector.control_type:
        search_params["ControlType"] = selector.control_type
    if selector.depth != 0xFFFFFFFF:
        search_params["searchDepth"] = selector.depth
    if selector.index > 1:
        search_params["foundIndex"] = selector.index

    # Get parent or root
    if selector.parent_handle:
        parent = auto.ControlFromHandle(selector.parent_handle)
        if not parent:
            return None
        search_params["searchFromControl"] = parent
    else:
        search_params["searchFromControl"] = auto.GetRootControl()

    # Find using generic Control
    return auto.Control(**search_params)


def get_control_by_handle(handle: int) -> Optional[auto.Control]:
    """Get a control by its handle.

    Args:
        handle: NativeWindowHandle of the control.

    Returns:
        Control object or None if not found.
    """
    if not handle:
        return None
    try:
        return auto.ControlFromHandle(handle)
    except Exception:
        return None


def format_error(
    code: str,
    message: str,
    suggestions: Optional[List[str]] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Format an error response.

    Args:
        code: Error code identifier.
        message: Human-readable error message.
        suggestions: List of suggestions to resolve the error.
        context: Additional context about the error.

    Returns:
        Formatted error dictionary.
    """
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "suggestions": suggestions or [],
            "context": context or {},
        }
    }


def format_success(data: Any = None) -> Dict[str, Any]:
    """Format a success response.

    Args:
        data: Optional data to include in the response.

    Returns:
        Formatted success dictionary.
    """
    return {
        "success": True,
        "data": data,
    }
