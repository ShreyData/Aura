import pyperclip
import structlog
from aura.tools.base import Tool, ToolResult, RiskLevel
from aura.tools.registry import register_tool

logger = structlog.get_logger()


@register_tool
class ReadClipboardTool(Tool):
    name = "read_clipboard"
    description = "Reads the current contents of the system clipboard."
    risk_level = RiskLevel.LOW
    enabled_platforms = ["all"]
    parameters = {"type": "object", "properties": {}}

    async def execute(self) -> ToolResult:
        try:
            content = pyperclip.paste()
            return ToolResult(success=True, output=content)
        except Exception as e:
            logger.error("read_clipboard_failed", error=str(e))
            return ToolResult(success=False, output=None, error=str(e))


@register_tool
class WriteClipboardTool(Tool):
    name = "write_clipboard"
    description = "Writes text to the system clipboard."
    risk_level = RiskLevel.MEDIUM
    enabled_platforms = ["all"]
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to write to the clipboard",
            }
        },
        "required": ["text"],
    }

    async def execute(self, text: str) -> ToolResult:
        try:
            pyperclip.copy(text)
            return ToolResult(
                success=True, output="Text copied to clipboard successfully."
            )
        except Exception as e:
            logger.error("write_clipboard_failed", error=str(e))
            return ToolResult(success=False, output=None, error=str(e))
