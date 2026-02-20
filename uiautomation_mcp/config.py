# -*- coding: utf-8 -*-
"""Configuration management for UIAutomation MCP Server."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Server configuration."""
    log_level: str = "INFO"
    default_timeout: int = 10
    admin_check: bool = True
    confirmation_enabled: bool = True
    screenshot_dir: str = "./screenshots"

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            log_level=os.getenv("UIAUTOMATION_LOG_LEVEL", "INFO"),
            default_timeout=int(os.getenv("UIAUTOMATION_TIMEOUT", "10")),
            admin_check=os.getenv("UIAUTOMATION_ADMIN_CHECK", "true").lower() == "true",
            confirmation_enabled=os.getenv("UIAUTOMATION_CONFIRMATION_ENABLED", "true").lower() == "true",
            screenshot_dir=os.getenv("UIAUTOMATION_SCREENSHOT_DIR", "./screenshots"),
        )


# Global config instance
config = Config.from_env()
