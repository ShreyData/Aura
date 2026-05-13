import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import chardet
import structlog

from aura.config import get_config
from aura.tools.base import RiskLevel, Tool, ToolResult
from aura.tools.registry import register_tool

logger = structlog.get_logger()

MAX_FILE_SIZE = 1 * 1024 * 1024  # 1MB


def _validate_path(path: str) -> Path:
    """
    Validates a path against the workspace jail.
    Returns the resolved Path object if valid, otherwise raises PermissionError.
    """
    config = get_config()
    workspace = config.workspace_path.expanduser().resolve()
    
    target_path = Path(path).expanduser()
    if not target_path.is_absolute():
        target_path = (workspace / target_path).resolve()
    else:
        target_path = target_path.resolve()

    if config.allow_system_paths:
        return target_path

    # Ensure target_path is within workspace
    if not str(target_path).startswith(str(workspace)):
        raise PermissionError(f"Access denied: Path {path} is outside the workspace jail.")

    return target_path


@register_tool
class ReadFileTool(Tool):
    name = "read_file"
    description = "Reads the content of a file within the workspace. Handles up to 1MB."
    risk_level = RiskLevel.LOW
    enabled_platforms = ["all"]
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to read"}
        },
        "required": ["path"]
    }

    async def execute(self, path: str) -> ToolResult:
        try:
            target_path = _validate_path(path)
            
            if not target_path.exists():
                return ToolResult(success=False, output=None, error=f"File not found: {path}")
            
            if not target_path.is_file():
                return ToolResult(success=False, output=None, error=f"Not a file: {path}")

            size = target_path.stat().st_size
            if size > MAX_FILE_SIZE:
                return ToolResult(success=False, output=None, error=f"File too large: {size} bytes (max {MAX_FILE_SIZE})")

            with open(target_path, "rb") as f:
                raw_data = f.read()
            
            # Detect encoding using chardet
            detection = chardet.detect(raw_data)
            encoding = detection.get("encoding") or "utf-8"
            
            content = raw_data.decode(encoding, errors="replace")
            return ToolResult(success=True, output=content)
            
        except PermissionError as e:
            return ToolResult(success=False, output=None, error=str(e))
        except Exception as e:
            logger.error("read_file_failed", path=path, error=str(e))
            return ToolResult(success=False, output=None, error=str(e))


@register_tool
class ListDirectoryTool(Tool):
    name = "list_directory"
    description = "Lists the contents of a directory within the workspace."
    risk_level = RiskLevel.LOW
    enabled_platforms = ["all"]
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the directory to list"}
        },
        "required": ["path"]
    }

    async def execute(self, path: str = ".") -> ToolResult:
        try:
            target_path = _validate_path(path)
            
            if not target_path.exists():
                return ToolResult(success=False, output=None, error=f"Directory not found: {path}")
            
            if not target_path.is_dir():
                return ToolResult(success=False, output=None, error=f"Not a directory: {path}")

            items = []
            for entry in os.scandir(target_path):
                items.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size": entry.stat().st_size if entry.is_file() else None
                })
            
            return ToolResult(success=True, output=items)
            
        except PermissionError as e:
            return ToolResult(success=False, output=None, error=str(e))
        except Exception as e:
            logger.error("list_directory_failed", path=path, error=str(e))
            return ToolResult(success=False, output=None, error=str(e))


@register_tool
class WriteFileTool(Tool):
    name = "write_file"
    description = "Writes content to a file. Creates parent directories if they do not exist."
    risk_level = RiskLevel.HIGH
    enabled_platforms = ["all"]
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to write"},
            "content": {"type": "string", "description": "Content to write to the file"}
        },
        "required": ["path", "content"]
    }

    async def execute(self, path: str, content: str) -> ToolResult:
        try:
            target_path = _validate_path(path)
            
            # Ensure parent directories exist
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            return ToolResult(success=True, output=f"Successfully wrote to {path}")
            
        except PermissionError as e:
            return ToolResult(success=False, output=None, error=str(e))
        except Exception as e:
            logger.error("write_file_failed", path=path, error=str(e))
            return ToolResult(success=False, output=None, error=str(e))


@register_tool
class DeleteFileTool(Tool):
    name = "delete_file"
    description = "Permanently deletes a file within the workspace."
    risk_level = RiskLevel.HIGH
    enabled_platforms = ["all"]
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to delete"}
        },
        "required": ["path"]
    }

    async def execute(self, path: str) -> ToolResult:
        try:
            target_path = _validate_path(path)
            
            if not target_path.exists():
                return ToolResult(success=False, output=None, error=f"File not found: {path}")
            
            if target_path.is_file():
                target_path.unlink()
            elif target_path.is_dir():
                shutil.rmtree(target_path)
            
            return ToolResult(success=True, output=f"Successfully deleted {path}")
            
        except PermissionError as e:
            return ToolResult(success=False, output=None, error=str(e))
        except Exception as e:
            logger.error("delete_file_failed", path=path, error=str(e))
            return ToolResult(success=False, output=None, error=str(e))


@register_tool
class MoveFileTool(Tool):
    name = "move_file"
    description = "Moves or renames a file or directory within the workspace."
    risk_level = RiskLevel.MEDIUM
    enabled_platforms = ["all"]
    parameters = {
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Current path of the file/directory"},
            "destination": {"type": "string", "description": "Target path for the move/rename"}
        },
        "required": ["source", "destination"]
    }

    async def execute(self, source: str, destination: str) -> ToolResult:
        try:
            src_path = _validate_path(source)
            dest_path = _validate_path(destination)
            
            if not src_path.exists():
                return ToolResult(success=False, output=None, error=f"Source not found: {source}")
            
            # Ensure destination parent exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.move(str(src_path), str(dest_path))
            
            return ToolResult(success=True, output=f"Successfully moved {source} to {destination}")
            
        except PermissionError as e:
            return ToolResult(success=False, output=None, error=str(e))
        except Exception as e:
            logger.error("move_file_failed", source=source, destination=destination, error=str(e))
            return ToolResult(success=False, output=None, error=str(e))
