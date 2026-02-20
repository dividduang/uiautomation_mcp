# -*- coding: utf-8 -*-
"""Tests for UIAutomation MCP tools.

Note: These tests mock uiautomation since actual UI requires Windows GUI.
The tests verify:
1. Tool modules can be imported
2. Tools can be registered with FastMCP
3. Core helper functions work correctly
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock


class TestControlInfo:
    """Test ControlInfo model."""

    def test_control_info_creation(self):
        """Test creating ControlInfo with all fields."""
        from uiautomation_mcp.models import ControlInfo

        info = ControlInfo(
            handle=12345,
            name="Test Window",
            class_name="WindowClass",
            control_type="WindowControl",
            automation_id="window1",
            process_id=999,
            enabled=True,
            visible=True,
            rect={"left": 0, "top": 0, "right": 800, "bottom": 600},
        )

        assert info.handle == 12345
        assert info.name == "Test Window"
        assert info.class_name == "WindowClass"
        assert info.control_type == "WindowControl"
        assert info.automation_id == "window1"
        assert info.process_id == 999
        assert info.enabled is True
        assert info.visible is True
        assert info.rect is not None

    def test_control_info_defaults(self):
        """Test ControlInfo default values."""
        from uiautomation_mcp.models import ControlInfo

        info = ControlInfo(handle=1)

        assert info.name == ""
        assert info.class_name == ""
        assert info.control_type == ""
        assert info.automation_id == ""
        assert info.process_id == 0
        assert info.enabled is True
        assert info.visible is True


class TestControlSelector:
    """Test ControlSelector model."""

    def test_selector_creation(self):
        """Test creating ControlSelector with search parameters."""
        from uiautomation_mcp.models import ControlSelector

        selector = ControlSelector(
            name="Button",
            class_name="ButtonClass",
            depth=5,
            index=2,
        )

        assert selector.name == "Button"
        assert selector.class_name == "ButtonClass"
        assert selector.depth == 5
        assert selector.index == 2

    def test_selector_defaults(self):
        """Test ControlSelector default values."""
        from uiautomation_mcp.models import ControlSelector

        selector = ControlSelector()

        assert selector.name is None
        assert selector.class_name is None
        assert selector.parent_handle is None
        assert selector.depth == 0xFFFFFFFF
        assert selector.index == 1


class TestConfirmationRequest:
    """Test ConfirmationRequest model."""

    def test_confirmation_creation(self):
        """Test creating a ConfirmationRequest."""
        from uiautomation_mcp.models import ConfirmationRequest

        request = ConfirmationRequest(
            tool="ui_close_window",
            details={"windowName": "Test"},
            message="Close window?",
            confirmation_token="abc123",
        )

        assert request.tool == "ui_close_window"
        assert request.details == {"windowName": "Test"}
        assert request.message == "Close window?"
        assert request.confirmation_token == "abc123"
        assert request.type == "confirmation_required"


class TestConfig:
    """Test configuration management."""

    def test_default_config(self):
        """Test default configuration values."""
        from uiautomation_mcp.config import config

        # These are the default values
        assert config.confirmation_enabled is True
        assert config.admin_check is True

    def test_config_can_be_modified(self):
        """Test that config can be modified."""
        from uiautomation_mcp.config import config

        original = config.confirmation_enabled
        config.confirmation_enabled = False
        assert config.confirmation_enabled is False
        config.confirmation_enabled = original


class TestCoreHelpers:
    """Test core helper functions."""

    def test_format_error(self):
        """Test error response formatting."""
        from uiautomation_mcp.core import format_error

        result = format_error(
            "TEST_ERROR",
            "Test error message",
            ["Suggestion 1", "Suggestion 2"],
            {"key": "value"},
        )

        assert result["success"] is False
        assert result["error"]["code"] == "TEST_ERROR"
        assert result["error"]["message"] == "Test error message"
        assert len(result["error"]["suggestions"]) == 2
        assert result["error"]["context"]["key"] == "value"

    def test_format_success(self):
        """Test success response formatting."""
        from uiautomation_mcp.core import format_success

        result = format_success({"key": "value"})

        assert result["success"] is True
        assert result["data"]["key"] == "value"

    def test_format_success_no_data(self):
        """Test success response without data."""
        from uiautomation_mcp.core import format_success

        result = format_success()

        assert result["success"] is True
        assert result["data"] is None

    def test_is_dangerous_tool(self):
        """Test dangerous tool detection."""
        from uiautomation_mcp.core import is_dangerous_tool

        assert is_dangerous_tool("ui_close_window") is True
        assert is_dangerous_tool("ui_terminate_process") is True
        assert is_dangerous_tool("ui_click") is False
        assert is_dangerous_tool("ui_find_window") is False

    def test_create_confirmation(self):
        """Test creating a confirmation request."""
        from uiautomation_mcp.core import create_confirmation

        request = create_confirmation(
            "ui_close_window",
            {"handle": 123},
            "Close this window?",
        )

        assert request.tool == "ui_close_window"
        assert request.details == {"handle": 123}
        assert request.message == "Close this window?"
        assert request.confirmation_token is not None
        assert len(request.confirmation_token) == 8

    def test_confirm_operation_approved(self):
        """Test confirming an operation that is approved."""
        from uiautomation_mcp.core import create_confirmation, confirm_operation

        request = create_confirmation("ui_close_window", {}, "Test")
        token = request.confirmation_token

        result = confirm_operation(token, True)

        assert result is not None
        assert result.tool == "ui_close_window"

    def test_confirm_operation_rejected(self):
        """Test confirming an operation that is rejected."""
        from uiautomation_mcp.core import create_confirmation, confirm_operation

        request = create_confirmation("ui_close_window", {}, "Test")
        token = request.confirmation_token

        result = confirm_operation(token, False)

        assert result is None

    def test_confirm_operation_invalid_token(self):
        """Test confirming with invalid token."""
        from uiautomation_mcp.core import confirm_operation

        result = confirm_operation("invalid_token", True)

        assert result is None

    def test_clear_pending_confirmations(self):
        """Test clearing pending confirmations."""
        from uiautomation_mcp.core import (
            create_confirmation,
            clear_pending_confirmations,
            get_pending_confirmation,
        )

        create_confirmation("ui_close_window", {}, "Test1")
        create_confirmation("ui_terminate_process", {}, "Test2")

        clear_pending_confirmations()

        # All should be cleared
        assert get_pending_confirmation("any") is None


class TestDiscoveryToolsRegistration:
    """Test discovery tools can be registered."""

    @patch("uiautomation_mcp.core.auto")
    def test_register_discovery_tools(self, mock_auto):
        """Test that discovery tools can be registered with FastMCP."""
        from mcp.server.fastmcp import FastMCP
        from uiautomation_mcp.tools.discovery import register_discovery_tools

        mcp = FastMCP("test-server")
        register_discovery_tools(mcp)

        # If we get here, registration succeeded
        assert True

    @patch("uiautomation_mcp.core.auto")
    def test_register_interaction_tools(self, mock_auto):
        """Test that interaction tools can be registered with FastMCP."""
        from mcp.server.fastmcp import FastMCP
        from uiautomation_mcp.tools.interaction import register_interaction_tools

        mcp = FastMCP("test-server")
        register_interaction_tools(mcp)

        # If we get here, registration succeeded
        assert True

    @patch("uiautomation_mcp.core.auto")
    def test_register_query_tools(self, mock_auto):
        """Test that query tools can be registered with FastMCP."""
        from mcp.server.fastmcp import FastMCP
        from uiautomation_mcp.tools.query import register_query_tools

        mcp = FastMCP("test-server")
        register_query_tools(mcp)

        # If we get here, registration succeeded
        assert True

    @patch("uiautomation_mcp.core.auto")
    def test_register_pattern_tools(self, mock_auto):
        """Test that pattern tools can be registered with FastMCP."""
        from mcp.server.fastmcp import FastMCP
        from uiautomation_mcp.tools.patterns import register_pattern_tools

        mcp = FastMCP("test-server")
        register_pattern_tools(mcp)

        # If we get here, registration succeeded
        assert True

    @patch("uiautomation_mcp.core.auto")
    def test_register_helper_tools(self, mock_auto):
        """Test that helper tools can be registered with FastMCP."""
        from mcp.server.fastmcp import FastMCP
        from uiautomation_mcp.tools.helpers import register_helper_tools

        mcp = FastMCP("test-server")
        register_helper_tools(mcp)

        # If we get here, registration succeeded
        assert True


class TestControlToInfo:
    """Test control_to_info function with mocked controls."""

    @patch("uiautomation_mcp.core.auto")
    def test_control_to_info(self, mock_auto):
        """Test converting a control to ControlInfo."""
        from uiautomation_mcp.core import control_to_info

        # Create mock control
        mock_control = MagicMock()
        mock_control.NativeWindowHandle = 12345
        mock_control.Name = "Test Control"
        mock_control.ClassName = "TestClass"
        mock_control.ControlTypeName = "ButtonControl"
        mock_control.AutomationId = "testButton"
        mock_control.ProcessId = 9999
        mock_control.IsEnabled = True
        mock_control.IsOffscreen = False

        # Mock BoundingRectangle
        mock_rect = MagicMock()
        mock_rect.left = 0
        mock_rect.top = 0
        mock_rect.right = 100
        mock_rect.bottom = 50
        mock_control.BoundingRectangle = mock_rect

        info = control_to_info(mock_control)

        assert info.handle == 12345
        assert info.name == "Test Control"
        assert info.class_name == "TestClass"
        assert info.control_type == "ButtonControl"
        assert info.automation_id == "testButton"
        assert info.process_id == 9999
        assert info.enabled is True
        assert info.visible is True

    @patch("uiautomation_mcp.core.auto")
    def test_control_to_info_with_none_properties(self, mock_auto):
        """Test converting a control with None properties."""
        from uiautomation_mcp.core import control_to_info

        # Create mock control with None properties
        mock_control = MagicMock()
        mock_control.NativeWindowHandle = None
        mock_control.Name = None
        mock_control.ClassName = None
        mock_control.ControlTypeName = None
        mock_control.AutomationId = None
        mock_control.ProcessId = None
        mock_control.IsEnabled = None
        mock_control.IsOffscreen = None
        mock_control.BoundingRectangle = None

        info = control_to_info(mock_control)

        assert info.handle == 0
        assert info.name == ""
        assert info.class_name == ""
        assert info.control_type == ""
        assert info.automation_id == ""
        assert info.process_id == 0
        assert info.enabled is True
        assert info.visible is True


class TestEnums:
    """Test enum models."""

    def test_mouse_button_enum(self):
        """Test MouseButton enum values."""
        from uiautomation_mcp.models import MouseButton

        assert MouseButton.LEFT.value == "left"
        assert MouseButton.RIGHT.value == "right"
        assert MouseButton.MIDDLE.value == "middle"

    def test_scroll_direction_enum(self):
        """Test ScrollDirection enum values."""
        from uiautomation_mcp.models import ScrollDirection

        assert ScrollDirection.UP.value == "up"
        assert ScrollDirection.DOWN.value == "down"
        assert ScrollDirection.LEFT.value == "left"
        assert ScrollDirection.RIGHT.value == "right"

    def test_expand_collapse_action_enum(self):
        """Test ExpandCollapseAction enum values."""
        from uiautomation_mcp.models import ExpandCollapseAction

        assert ExpandCollapseAction.EXPAND.value == "expand"
        assert ExpandCollapseAction.COLLAPSE.value == "collapse"


class TestResponseModels:
    """Test response model classes."""

    def test_error_response(self):
        """Test ErrorResponse model."""
        from uiautomation_mcp.models import ErrorResponse

        response = ErrorResponse(
            error={"code": "TEST_ERROR", "message": "Test error"}
        )

        assert response.success is False
        assert response.error["code"] == "TEST_ERROR"

    def test_success_response(self):
        """Test SuccessResponse model."""
        from uiautomation_mcp.models import SuccessResponse

        response = SuccessResponse(data={"key": "value"})

        assert response.success is True
        assert response.data["key"] == "value"

    def test_success_response_no_data(self):
        """Test SuccessResponse model without data."""
        from uiautomation_mcp.models import SuccessResponse

        response = SuccessResponse()

        assert response.success is True
        assert response.data is None


class TestToolImports:
    """Test that all tool modules can be imported."""

    def test_import_discovery(self):
        """Test importing discovery tools module."""
        from uiautomation_mcp.tools.discovery import register_discovery_tools
        assert callable(register_discovery_tools)

    def test_import_interaction(self):
        """Test importing interaction tools module."""
        from uiautomation_mcp.tools.interaction import register_interaction_tools
        assert callable(register_interaction_tools)

    def test_import_query(self):
        """Test importing query tools module."""
        from uiautomation_mcp.tools.query import register_query_tools
        assert callable(register_query_tools)

    def test_import_patterns(self):
        """Test importing patterns tools module."""
        from uiautomation_mcp.tools.patterns import register_pattern_tools
        assert callable(register_pattern_tools)

    def test_import_helpers(self):
        """Test importing helper tools module."""
        from uiautomation_mcp.tools.helpers import register_helper_tools
        assert callable(register_helper_tools)

    def test_import_tools_init(self):
        """Test importing tools __init__ module exports."""
        from uiautomation_mcp import tools

        # Check all expected exports are present
        assert hasattr(tools, 'register_discovery_tools')
        assert hasattr(tools, 'register_interaction_tools')
        assert hasattr(tools, 'register_query_tools')
        assert hasattr(tools, 'register_pattern_tools')
        assert hasattr(tools, 'register_helper_tools')
        assert callable(tools.register_discovery_tools)


class TestPackageInit:
    """Test package __init__ imports."""

    def test_package_imports(self):
        """Test that package exports expected names."""
        import uiautomation_mcp

        # Check that __all__ is defined
        assert hasattr(uiautomation_mcp, "__all__")
        assert "__version__" in uiautomation_mcp.__all__


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
