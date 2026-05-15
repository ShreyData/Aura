import subprocess
from typing import List

import structlog

from aura.tools.base import RiskLevel, Tool, ToolResult
from aura.tools.registry import register_tool

logger = structlog.get_logger()

# Commands that are strictly forbidden regardless of approval
COMMAND_BLOCKLIST = [
    "sudo",
    "su",
    "rm -rf /",
    "mkfs",
    "format C:",
    "del /f /s",
]


@register_tool
class RunCommandTool(Tool):
    name = "run_command"
    description = (
        "Executes a sandboxed shell command on the local system. "
        "The command is executed with shell=False for security. "
        "Dangerous system commands are blocked."
    )
    risk_level = RiskLevel.HIGH
    enabled_platforms = ["all"]
    parameters = {
        "type": "object",
        "properties": {
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "The command and its arguments as a list (e.g., ['ls', '-la'])",
            }
        },
        "required": ["args"],
    }

    async def execute(self, args: List[str]) -> ToolResult:
        if not args:
            return ToolResult(success=False, output=None, error="No command provided.")

        # 1. Blocklist Validation
        # Join args to check for blocked patterns in the full string
        full_command = " ".join(args).lower()
        for blocked in COMMAND_BLOCKLIST:
            if full_command.startswith(blocked.lower()):
                logger.warning("blocked_command_attempted", command=full_command)
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Security Error: The command '{blocked}' is strictly forbidden.",
                )

        # 2. Execution
        try:
            logger.info("executing_shell_command", command=args)

            # shell=False is mandatory to prevent injection
            # timeout=30.0 prevents long-running or hanging processes
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                shell=False,
                timeout=30.0,
                check=False,  # We want to return exit code and stderr even if it fails
            )

            output = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }

            return ToolResult(
                success=(result.returncode == 0),
                output=output,
                error=result.stderr if result.returncode != 0 else None,
            )

        except subprocess.TimeoutExpired:
            logger.error("command_timeout", command=args)
            return ToolResult(
                success=False,
                output=None,
                error="Execution failed: The command timed out after 30 seconds.",
            )
        except FileNotFoundError:
            logger.error("command_not_found", command=args[0])
            return ToolResult(
                success=False,
                output=None,
                error=f"Execution failed: The command '{args[0]}' was not found.",
            )
        except Exception as e:
            logger.error("command_execution_error", command=args, error=str(e))
            return ToolResult(
                success=False, output=None, error=f"Execution failed: {str(e)}"
            )
