from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RiskLevel(Enum):
    """
    Defines the security risk level of a tool.
    Used to determine if user approval is required before execution.
    """

    LOW = "low"  # Read-only, no side effects. Never requires approval.
    MEDIUM = "medium"  # Creates or modifies. Approval configurable (default: yes).
    HIGH = "high"  # Destructive or executes code. Always requires approval.


@dataclass
class ToolResult:
    """
    Standardized result returned by all tools after execution.
    """

    success: bool
    output: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    """
    Abstract Base Class that every Aura tool must implement.
    """

    name: str  # snake_case, globally unique across all tools
    description: str  # Shown to Gemma 4 in the system prompt
    parameters: Dict[str, Any]  # JSON Schema object (type: object, properties: {...})
    risk_level: RiskLevel
    enabled_platforms: List[str]  # ["windows", "macos", "linux"] or ["all"]
    version: str = "1.0.0"

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        Executes the tool's core logic with the provided arguments.
        Must be implemented by all subclasses.
        """
        pass

    def is_available(self) -> bool:
        """
        Returns True if the tool's dependencies are met and it can be used.
        Override this to perform runtime checks (e.g., checking if a CLI tool is installed).
        """
        return True
