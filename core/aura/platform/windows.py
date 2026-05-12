import ctypes
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List

import psutil
import structlog

try:
    import win32api
    import win32con
    import win32gui
    import win32process
except ImportError:
    # These will be available in the target environment
    win32api = None
    win32con = None
    win32gui = None
    win32process = None

from aura.platform.base import PlatformAdapter

logger = structlog.get_logger()


class WindowsAdapter(PlatformAdapter):
    """
    Windows-specific implementation of the PlatformAdapter.
    Uses pywin32, psutil, and ctypes for OS interaction.
    """

    def get_active_window_title(self) -> str:
        """
        Returns the title of the foreground window.
        """
        if not win32gui:
            return "Unknown"
        try:
            hwnd = win32gui.GetForegroundWindow()
            return win32gui.GetWindowText(hwnd)
        except Exception as e:
            logger.error("win32_get_active_window_failed", error=str(e))
            return "Unknown"

    def get_running_processes(self) -> List[str]:
        """
        Returns a list of all running process names.
        """
        processes = []
        for proc in psutil.process_iter(["name"]):
            try:
                processes.append(proc.info["name"])
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return processes

    def open_application(self, name: str) -> bool:
        """
        Launches an application or file using the Windows shell.
        """
        try:
            # win32api.ShellExecute is the safest way to "launch" things on Windows
            # as it handles executables, shortcuts, and registered file types.
            if win32api:
                win32api.ShellExecute(0, "open", name, None, None, win32con.SW_SHOWNORMAL)
                return True
            else:
                # Fallback to os.startfile if pywin32 is missing
                os.startfile(name)
                return True
        except Exception as e:
            logger.error("win32_open_app_failed", name=name, error=str(e))
            return False

    def get_default_workspace_path(self) -> Path:
        """
        Returns ~/Documents/AuraWorkspace.
        """
        return Path.home() / "Documents" / "AuraWorkspace"

    def send_notification(self, title: str, body: str) -> None:
        """
        Sends a desktop notification using a PowerShell script.
        This avoids external Python dependencies for toasts.
        """
        # Escaping for PowerShell
        t = title.replace("'", "''")
        b = body.replace("'", "''")
        
        powershell_cmd = (
            f"$title = '{t}'; $body = '{b}'; "
            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null; "
            "$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
            "$textNodes = $template.GetElementsByTagName('text'); "
            "$textNodes.Item(0).AppendChild($template.CreateTextNode($title)) > $null; "
            "$textNodes.Item(1).AppendChild($template.CreateTextNode($body)) > $null; "
            "$toast = [Windows.UI.Notifications.ToastNotification]::new($template); "
            "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Aura').Show($toast);"
        )
        
        try:
            subprocess.run(
                ["powershell", "-Command", powershell_cmd],
                capture_output=True,
                check=False,
                shell=False
            )
        except Exception as e:
            logger.error("win32_notification_failed", error=str(e))

    def get_display_info(self) -> List[Dict[str, Any]]:
        """
        Returns resolution and info for all connected monitors.
        """
        displays = []
        if not win32api:
            return displays

        try:
            monitors = win32api.EnumDisplayMonitors()
            for monitor in monitors:
                handle = monitor[0]
                info = win32api.GetMonitorInfo(handle)
                displays.append({
                    "monitor_area": info["Monitor"],
                    "work_area": info["Work"],
                    "is_primary": info["Flags"] & win32con.MONITORINFOF_PRIMARY != 0
                })
        except Exception as e:
            logger.error("win32_get_display_info_failed", error=str(e))
            
        return displays

    def lock_screen(self) -> None:
        """
        Locks the Windows workstation.
        """
        try:
            ctypes.windll.user32.LockWorkStation()
        except Exception as e:
            logger.error("win32_lock_screen_failed", error=str(e))

    def get_idle_time_seconds(self) -> float:
        """
        Returns user idle time in seconds using GetLastInputInfo.
        """
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("dwTime", ctypes.c_uint),
            ]

        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return millis / 1000.0
        else:
            return 0.0
