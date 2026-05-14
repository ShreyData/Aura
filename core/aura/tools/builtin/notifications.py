import structlog
from aura.tools.base import Tool, ToolResult, RiskLevel
from aura.tools.registry import register_tool
from aura.platform.factory import get_platform

logger = structlog.get_logger()

@register_tool
class SendNotificationTool(Tool):
    name = "send_notification"
    description = "Displays a native desktop notification."
    risk_level = RiskLevel.LOW
    enabled_platforms = ["all"]
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "The title of the notification"},
            "body": {"type": "string", "description": "The body text of the notification"}
        },
        "required": ["title", "body"]
    }

    async def execute(self, title: str, body: str) -> ToolResult:
        try:
            platform = get_platform()
            platform.send_notification(title, body)
            return ToolResult(success=True, output="Notification sent successfully.")
        except Exception as e:
            logger.error("send_notification_failed", error=str(e))
            return ToolResult(success=False, output=None, error=str(e))
