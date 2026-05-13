import importlib
import pkgutil
import sys
from typing import Any, Dict, List, Optional, Type

import structlog

from aura.tools.base import Tool

logger = structlog.get_logger()

# Global registry to store tool classes discovered via @register_tool
_TOOL_CLASSES: Dict[str, Type[Tool]] = {}


def register_tool(cls: Type[Tool]) -> Type[Tool]:
    """
    Decorator to register a tool class with the global registry.
    Must be used on classes that inherit from Tool.
    """
    if not issubclass(cls, Tool):
        logger.error("tool_registration_failed", class_name=cls.__name__, error="Class must inherit from Tool")
        return cls

    # Ensure the class has a name attribute defined
    name = getattr(cls, "name", None)
    if not name:
        logger.error("tool_registration_failed", class_name=cls.__name__, error="Tool missing 'name' attribute")
        return cls

    _TOOL_CLASSES[name] = cls
    logger.debug("tool_class_registered", name=name, class_name=cls.__name__)
    return cls


class ToolRegistry:
    """
    Handles the discovery, registration, and management of Aura tools.
    Filters tools based on the current operating system.
    """

    def __init__(self) -> None:
        self.tools: Dict[str, Tool] = {}
        self._discover_and_initialize()

    def _discover_and_initialize(self) -> None:
        """
        Scans builtin and plugin packages, filters by platform compatibility,
        and initializes available tools.
        """
        # 1. Discover tool classes by importing packages
        # This triggers the @register_tool decorators in individual tool modules
        self._scan_package("aura.tools.builtin")
        self._scan_package("aura.tools.plugins")

        # 2. Determine current platform
        # Note: aura.platform.factory.get_platform() is implemented in Step 2.4.
        # We use sys.platform mapping as a reliable bootstrap fallback.
        current_platform = sys.platform
        if current_platform == "win32":
            current_platform = "windows"
        elif current_platform == "darwin":
            current_platform = "macos"

        try:
            # This import will be valid after Step 2.4 is completed
            from aura.platform.factory import get_platform

            # If the factory is available, we could use the instance for more 
            # granular capability checks in the future.
            platform_adapter = get_platform()
            logger.debug("platform_adapter_detected", platform=current_platform)
        except (ImportError, Exception):
            logger.debug("platform_factory_not_yet_ready_using_fallback")

        # 3. Filter and instantiate tools
        for name, cls in _TOOL_CLASSES.items():
            # Filter by platform: ["all"], ["windows"], ["macos"], or ["linux"]
            if "all" in cls.enabled_platforms or current_platform in cls.enabled_platforms:
                try:
                    instance = cls()
                    if instance.is_available():
                        self.tools[name] = instance
                        logger.debug("tool_loaded", name=name)
                    else:
                        logger.debug("tool_unavailable_skipped", name=name)
                except Exception as e:
                    logger.error("tool_initialization_failed", name=name, error=str(e))
            else:
                logger.debug("tool_platform_mismatch_skipped", name=name, platform=current_platform)

        logger.info("tool_registry_ready", total_tools=len(self.tools))

    def _scan_package(self, package_name: str) -> None:
        """
        Recursively finds and imports all modules in a given package path
        to trigger registration decorators.
        """
        try:
            package = importlib.import_module(package_name)
            for _, module_name, is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
                importlib.import_module(module_name)
        except Exception as e:
            logger.warning("package_scan_error", package=package_name, error=str(e))

    def generate_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Returns a list of tool definitions as JSON Schema objects for LLM consumption.
        """
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            for t in self.tools.values()
        ]

    def get_tool(self, name: str) -> Optional[Tool]:
        """
        Retrieves a tool instance by its unique name.
        """
        return self.tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        Returns a summary list of all currently registered and available tools.
        """
        return [
            {
                "name": t.name,
                "description": t.description,
                "risk_level": t.risk_level.value,
                "version": t.version,
            }
            for t in self.tools.values()
        ]


# Singleton instance for easy access across the application
_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """
    Returns the global ToolRegistry singleton.
    """
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def reset_tool_registry() -> None:
    """
    Resets the ToolRegistry singleton. Useful for testing.
    """
    global _registry
    _registry = None
