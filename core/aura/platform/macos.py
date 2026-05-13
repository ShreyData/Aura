import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List

import psutil
import structlog

try:
    from AppKit import NSScreen, NSWorkspace
    from Foundation import (
        NSBundle,
        NSDictionary,
        NSDistributedNotificationCenter,
    )
    from UserNotifications import (
        UNUserNotificationCenter,
        UNMutableNotificationContent,
        UNNotificationRequest,
        UNTimeIntervalNotificationTrigger,
    )
    import Quartz
except ImportError:
    # These will be available in the target macOS environment
    NSScreen = None
    NSWorkspace = None
    NSBundle = None
    NSDictionary = None
    NSDistributedNotificationCenter = None
    UNUserNotificationCenter = None
    UNMutableNotificationContent = None
    UNNotificationRequest = None
    UNTimeIntervalNotificationTrigger = None
    Quartz = None

from aura.platform.base import PlatformAdapter

logger = structlog.get_logger()


class MacOSAdapter(PlatformAdapter):
    """
    macOS-specific implementation of the PlatformAdapter.
    Uses pyobjc (AppKit, Foundation, Quartz, UserNotifications) and psutil.
    """

    def get_active_window_title(self) -> str:
        """
        Returns the name of the frontmost application using NSWorkspace.
        """
        if not NSWorkspace:
            return "Unknown"
        try:
            workspace = NSWorkspace.sharedWorkspace()
            # Follow docs exactly: use activeApplication()
            active_app = workspace.activeApplication()
            if active_app and "NSApplicationName" in active_app:
                return active_app["NSApplicationName"]
            
            # Fallback to modern frontmostApplication if activeApplication fails
            modern_app = workspace.frontmostApplication()
            if modern_app:
                return modern_app.localizedName()
                
            return "Unknown"
        except Exception as e:
            logger.error("macos_get_active_window_failed", error=str(e))
            return "Unknown"

    def get_running_processes(self) -> List[str]:
        """
        Returns a list of all running process names using psutil.
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
        Launches an application by name or path using NSWorkspace.
        """
        if not NSWorkspace:
            # Fallback to shell 'open' command
            try:
                subprocess.run(["open", "-a", name], check=True, shell=False)
                return True
            except Exception:
                return False

        try:
            workspace = NSWorkspace.sharedWorkspace()
            return workspace.launchApplication_(name)
        except Exception as e:
            logger.error("macos_open_app_failed", name=name, error=str(e))
            return False

    def get_default_workspace_path(self) -> Path:
        """
        Returns ~/Documents/AuraWorkspace.
        """
        return Path.home() / "Documents" / "AuraWorkspace"

    def send_notification(self, title: str, body: str) -> None:
        """
        Sends a native macOS notification using UNUserNotificationCenter.
        """
        if not UNUserNotificationCenter:
            return

        try:
            content = UNMutableNotificationContent.alloc().init()
            content.setTitle_(title)
            content.setBody_(body)
            
            # Trigger immediately
            trigger = UNTimeIntervalNotificationTrigger.triggerWithTimeInterval_repeats_(1, False)
            
            request = UNNotificationRequest.requestWithIdentifier_content_trigger_(
                "AuraNotification", content, trigger
            )
            
            center = UNUserNotificationCenter.currentNotificationCenter()
            
            # Request authorization (normally done at startup, but here for completeness)
            def handler(granted, error):
                if granted:
                    center.addNotificationRequest_withCompletionHandler_(request, None)
            
            center.requestAuthorizationWithOptions_completionHandler_(
                (1 << 0) | (1 << 1) | (1 << 2), # Alert, Sound, Badge
                handler
            )
        except Exception as e:
            logger.error("macos_notification_failed", error=str(e))

    def get_display_info(self) -> List[Dict[str, Any]]:
        """
        Returns info for all connected screens using NSScreen.
        """
        displays = []
        if not NSScreen:
            return displays

        try:
            screens = NSScreen.screens()
            for screen in screens:
                frame = screen.frame()
                displays.append({
                    "resolution": {
                        "width": frame.size.width,
                        "height": frame.size.height
                    },
                    "is_primary": screen == NSScreen.mainScreen()
                })
        except Exception as e:
            logger.error("macos_get_display_info_failed", error=str(e))
            
        return displays

    def lock_screen(self) -> None:
        """
        Locks the macOS screen by calling the loginwindow display sleep command.
        """
        try:
            # Traditional method via loginwindow
            subprocess.run(
                ["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession", "-suspend"],
                check=False
            )
        except Exception as e:
            logger.error("macos_lock_screen_failed", error=str(e))

    def focus_window(self, title: str) -> bool:
        """
        Attempts to focus a window by its title using AppleScript.
        """
        script = f'tell application "System Events" to set frontmost of (every process whose name contains "{title}") to true'
        try:
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            return True
        except Exception as e:
            logger.error("macos_focus_window_failed", title=title, error=str(e))
            return False

    def get_idle_time_seconds(self) -> float:
        """
        Returns user idle time in seconds using Quartz.
        """
        if not Quartz:
            return 0.0
            
        try:
            # CGEventSourceSecondsSinceLastEventType(kCGEventSourceStateCombinedSessionState, kCGAnyInputEventType)
            idle_time = Quartz.CGEventSourceSecondsSinceLastEventType(
                Quartz.kCGEventSourceStateCombinedSessionState,
                Quartz.kCGAnyInputEventType
            )
            return float(idle_time)
        except Exception as e:
            logger.error("macos_get_idle_time_failed", error=str(e))
            return 0.0
