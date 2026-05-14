from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List


class PlatformAdapter(ABC):
    """
    Abstract base class for operating system specific operations.
    All platform implementations (Windows, macOS, Linux) must follow this interface.
    """

    @abstractmethod
    def get_active_window_title(self) -> str:
        """
        Returns the title of the currently focused/active window.
        """
        pass

    @abstractmethod
    def get_running_processes(self) -> List[str]:
        """
        Returns a list of names of all currently running processes.
        """
        pass

    @abstractmethod
    def open_application(self, name: str) -> bool:
        """
        Attempts to launch an application by name.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def get_default_workspace_path(self) -> Path:
        """
        Returns the platform-specific default path for the Aura workspace.
        """
        pass

    @abstractmethod
    def send_notification(self, title: str, body: str) -> None:
        """
        Displays a native desktop notification.
        """
        pass

    @abstractmethod
    def get_display_info(self) -> List[Dict[str, Any]]:
        """
        Returns information about connected displays (resolution, primary status, etc.).
        """
        pass

    @abstractmethod
    def lock_screen(self) -> None:
        """
        Triggers the OS-native screen lock.
        """
        pass

    @abstractmethod
    def focus_window(self, title: str) -> bool:
        """
        Attempts to bring a window with the given title to the foreground.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def get_idle_time_seconds(self) -> float:
        """
        Returns the number of seconds since the last user input (keyboard/mouse).
        """
        pass
