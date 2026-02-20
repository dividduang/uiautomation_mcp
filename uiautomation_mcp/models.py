# -*- coding: utf-8 -*-
"""Data models for UIAutomation MCP Server."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class ControlInfo(BaseModel):
    """Control information returned by discovery tools."""
    handle: int = Field(..., description="NativeWindowHandle for subsequent operations")
    name: str = Field("", description="Control name")
    class_name: str = Field("", alias="className", description="Windows class name")
    control_type: str = Field("", alias="controlType", description="Control type name")
    automation_id: str = Field("", alias="automationId", description="Automation ID")
    process_id: int = Field(0, alias="processId", description="Process ID")
    enabled: bool = Field(True, description="Whether control is enabled")
    visible: bool = Field(True, description="Whether control is visible")
    rect: Optional[Dict[str, int]] = Field(None, description="Bounding rectangle")

    class Config:
        populate_by_name = True


class ControlSelector(BaseModel):
    """Selector for finding controls."""
    parent_handle: Optional[int] = Field(None, alias="parentHandle", description="Parent control handle")
    control_type: Optional[str] = Field(None, alias="controlType", description="Control type to find")
    name: Optional[str] = Field(None, description="Exact name match")
    name_contains: Optional[str] = Field(None, alias="nameContains", description="Name contains")
    name_regex: Optional[str] = Field(None, alias="nameRegex", description="Name regex pattern")
    class_name: Optional[str] = Field(None, alias="className", description="Windows class name")
    automation_id: Optional[str] = Field(None, alias="automationId", description="Automation ID")
    depth: int = Field(0xFFFFFFFF, description="Search depth")
    index: int = Field(1, description="Nth matching control (1-based)")

    class Config:
        populate_by_name = True


class MouseButton(str, Enum):
    """Mouse button types."""
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


class ScrollDirection(str, Enum):
    """Scroll directions."""
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class ExpandCollapseAction(str, Enum):
    """Expand/Collapse actions."""
    EXPAND = "expand"
    COLLAPSE = "collapse"


class ConfirmationRequest(BaseModel):
    """Confirmation request for dangerous operations."""
    type: str = "confirmation_required"
    tool: str
    details: Dict[str, Any]
    message: str
    confirmation_token: str = Field(..., alias="confirmationToken")

    class Config:
        populate_by_name = True


class ErrorResponse(BaseModel):
    """Error response format."""
    success: bool = False
    error: Dict[str, Any]


class SuccessResponse(BaseModel):
    """Success response format."""
    success: bool = True
    data: Optional[Any] = None
