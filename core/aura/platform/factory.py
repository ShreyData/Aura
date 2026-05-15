import sys
from typing import Optional

import structlog

from aura.platform.base import PlatformAdapter

logger = structlog.get_logger()

# Cached instance of the platform adapter
_instance: Optional[PlatformAdapter] = None


def get_platform() -> PlatformAdapter:
    """
    Detects the current operating system and returns the corresponding
    PlatformAdapter implementation. The instance is cached after the first call.
    """
    global _instance

    if _instance is not None:
        return _instance

    platform = sys.platform

    if platform == "win32":
        from aura.platform.windows import WindowsAdapter

        _instance = WindowsAdapter()
    elif platform == "darwin":
        from aura.platform.macos import MacOSAdapter

        _instance = MacOSAdapter()
    elif platform.startswith("linux"):
        from aura.platform.linux import LinuxAdapter

        _instance = LinuxAdapter()
    else:
        logger.error("unsupported_platform", platform=platform)
        raise RuntimeError(f"Aura does not support the platform: {platform}")

    logger.debug("platform_adapter_initialized", platform=platform)
    return _instance
