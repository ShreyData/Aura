import webbrowser
from urllib.parse import urlparse
import structlog
from aura.tools.base import Tool, ToolResult, RiskLevel
from aura.tools.registry import register_tool

logger = structlog.get_logger()

@register_tool
class OpenUrlTool(Tool):
    name = "open_url"
    description = "Opens a URL in the default web browser. Only http and https schemes are allowed."
    risk_level = RiskLevel.MEDIUM
    enabled_platforms = ["all"]
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to open (must start with http:// or https://)"}
        },
        "required": ["url"]
    }

    async def execute(self, url: str) -> ToolResult:
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ["http", "https"]:
                return ToolResult(
                    success=False, 
                    output=None, 
                    error=f"Invalid URL scheme '{parsed.scheme}'. Only http and https are allowed for security."
                )
            
            # webbrowser.open is cross-platform
            webbrowser.open(url)
            return ToolResult(success=True, output=f"URL '{url}' opened in the default browser.")
        except Exception as e:
            logger.error("open_url_failed", url=url, error=str(e))
            return ToolResult(success=False, output=None, error=str(e))
