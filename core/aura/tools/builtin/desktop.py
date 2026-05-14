from typing import Any, Dict
import structlog

from aura.tools.base import Tool, ToolResult, RiskLevel
from aura.tools.registry import register_tool
from aura.platform.factory import get_platform

logger = structlog.get_logger()

@register_tool
class OpenApplicationTool(Tool):
    name = "open_application"
    description = "Launches a named application on the operating system."
    risk_level = RiskLevel.MEDIUM
    enabled_platforms = ["all"]
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The name or path of the application to open"}
        },
        "required": ["name"]
    }

    async def execute(self, name: str) -> ToolResult:
        try:
            platform = get_platform()
            success = platform.open_application(name)
            if success:
                return ToolResult(success=True, output=f"Application '{name}' launched successfully.")
            return ToolResult(success=False, output=None, error=f"Failed to launch application '{name}'.")
        except Exception as e:
            logger.error("open_application_failed", name=name, error=str(e))
            return ToolResult(success=False, output=None, error=str(e))

@register_tool
class FocusWindowTool(Tool):
    name = "focus_window"
    description = "Brings a window to the foreground by its title."
    risk_level = RiskLevel.LOW
    enabled_platforms = ["all"]
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "The title of the window to focus"}
        },
        "required": ["title"]
    }

    async def execute(self, title: str) -> ToolResult:
        try:
            platform = get_platform()
            success = platform.focus_window(title)
            if success:
                return ToolResult(success=True, output=f"Window '{title}' focused successfully.")
            return ToolResult(success=False, output=None, error=f"Window '{title}' not found or could not be focused.")
        except Exception as e:
            logger.error("focus_window_failed", title=title, error=str(e))
            return ToolResult(success=False, output=None, error=str(e))
