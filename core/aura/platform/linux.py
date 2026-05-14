import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List

import psutil
import structlog

try:
    # X11 Window detection
    from Xlib import X, display
    from Xlib.ext import saver
except ImportError:
    display = None
    X = None
    saver = None

try:
    # Notifications via D-Bus
    import dbus
except ImportError:
    dbus = None

from aura.platform.base import PlatformAdapter

logger = structlog.get_logger()


class LinuxAdapter(PlatformAdapter):
    """
    Linux-specific implementation of the PlatformAdapter.
    Handles both X11 and Wayland environments where possible.
    """

    def __init__(self) -> None:
        self.is_wayland = os.environ.get("WAYLAND_DISPLAY") is not None
        if self.is_wayland:
            logger.info("linux_platform_detected", display_server="Wayland")
        else:
            logger.info("linux_platform_detected", display_server="X11")

    def get_active_window_title(self) -> str:
        """
        Returns the title of the active window.
        On X11, uses python-xlib. On Wayland, this is restricted for security.
        """
        if self.is_wayland:
            # Wayland does not allow querying other windows by design for privacy
            return "Unknown (Wayland)"

        if not display:
            return "Unknown (Xlib missing)"

        try:
            d = display.Display()
            root = d.screen().root
            
            # Get the ID of the active window from the _NET_ACTIVE_WINDOW property
            active_window_id_prop = d.intern_atom("_NET_ACTIVE_WINDOW")
            res = root.get_full_property(active_window_id_prop, X.AnyPropertyType)
            
            if not res or not res.value:
                return "Unknown"
                
            window_id = res.value[0]
            window_obj = d.create_resource_object("window", window_id)
            
            # Try to get the window name (_NET_WM_NAME or WM_NAME)
            for atom_name in ["_NET_WM_NAME", "WM_NAME"]:
                atom = d.intern_atom(atom_name)
                name_res = window_obj.get_full_property(atom, 0)
                if name_res and name_res.value:
                    if isinstance(name_res.value, bytes):
                        return name_res.value.decode("utf-8", errors="ignore")
                    return str(name_res.value)
                    
            return "Unknown"
        except Exception as e:
            logger.error("linux_get_active_window_failed", error=str(e))
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
        Launches an application or file using xdg-open.
        """
        try:
            # xdg-open is the standard Linux way to open files or apps
            subprocess.run(["xdg-open", name], check=True, shell=False, capture_output=True)
            return True
        except Exception as e:
            logger.error("linux_open_app_failed", name=name, error=str(e))
            return False

    def get_default_workspace_path(self) -> Path:
        """
        Returns ~/AuraWorkspace as per Linux implementation notes.
        """
        return Path.home() / "AuraWorkspace"

    def send_notification(self, title: str, body: str) -> None:
        """
        Sends a native Linux desktop notification via D-Bus.
        """
        if not dbus:
            # Fallback to notify-send CLI if dbus-python is missing
            try:
                subprocess.run(["notify-send", title, body], check=False, shell=False)
            except Exception:
                pass
            return

        try:
            item = "org.freedesktop.Notifications"
            path = "/org/freedesktop/Notifications"
            interface = "org.freedesktop.Notifications"
            
            bus = dbus.SessionBus()
            notif = bus.get_object(item, path)
            notify_interface = dbus.Interface(notif, interface)
            
            # Notify(app_name, replaces_id, app_icon, summary, body, actions, hints, expire_timeout)
            notify_interface.Notify("Aura", 0, "", title, body, [], {}, -1)
        except Exception as e:
            logger.error("linux_notification_failed", error=str(e))

    def get_display_info(self) -> List[Dict[str, Any]]:
        """
        Returns info for all connected displays.
        On X11, uses Xlib. On Wayland, returns a basic list via sysfs or placeholder.
        """
        displays = []
        
        if self.is_wayland:
            # Wayland display info is harder to query directly from Python
            # We return a generic placeholder for now
            return [{"id": "wayland-0", "is_primary": True}]

        if not display:
            return displays

        try:
            d = display.Display()
            for i in range(d.screen_count()):
                screen = d.screen(i)
                displays.append({
                    "id": f"x11-{i}",
                    "resolution": {
                        "width": screen.width_in_pixels,
                        "height": screen.height_in_pixels
                    },
                    "is_primary": i == 0
                })
        except Exception as e:
            logger.error("linux_get_display_info_failed", error=str(e))
            
        return displays

    def lock_screen(self) -> None:
        """
        Locks the Linux screen using xdg-screensaver or loginctl.
        """
        # Try loginctl first (standard on systemd distros)
        try:
            subprocess.run(["loginctl", "lock-session"], check=False, shell=False)
            return
        except Exception:
            pass

        # Fallback to xdg-screensaver
        try:
            subprocess.run(["xdg-screensaver", "lock"], check=False, shell=False)
        except Exception as e:
            logger.error("linux_lock_screen_failed", error=str(e))

    def focus_window(self, title: str) -> bool:
        """
        Attempts to focus a window by its title using Xlib.
        """
        if self.is_wayland:
            return False

        if not display:
            return False

        try:
            d = display.Display()
            root = d.screen().root
            
            # Find the window
            window_id_prop = d.intern_atom("_NET_CLIENT_LIST")
            res = root.get_full_property(window_id_prop, X.AnyPropertyType)
            
            if not res or not res.value:
                return False
                
            for window_id in res.value:
                window_obj = d.create_resource_object("window", window_id)
                for atom_name in ["_NET_WM_NAME", "WM_NAME"]:
                    atom = d.intern_atom(atom_name)
                    name_res = window_obj.get_full_property(atom, 0)
                    if name_res and name_res.value:
                        name = ""
                        if isinstance(name_res.value, bytes):
                            name = name_res.value.decode("utf-8", errors="ignore")
                        else:
                            name = str(name_res.value)
                        
                        if title.lower() in name.lower():
                            # Focus the window
                            active_atom = d.intern_atom("_NET_ACTIVE_WINDOW")
                            ev = display.event.ClientMessage(
                                window=window_obj,
                                client_type=active_atom,
                                data=(32, [1, X.CurrentTime, 0, 0, 0])
                            )
                            root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
                            d.display.sync()
                            return True
            return False
        except Exception as e:
            logger.error("linux_focus_window_failed", title=title, error=str(e))
            return False

    def get_idle_time_seconds(self) -> float:
        """
        Returns user idle time in seconds.
        On X11, uses XScreenSaver extension. On Wayland, returns 0.
        """
        if self.is_wayland:
            return 0.0
            
        if not display or not saver:
            return 0.0
            
        try:
            d = display.Display()
            # Verify the extension is available
            if not d.has_extension("MIT-SCREEN-SAVER"):
                return 0.0
                
            info = saver.query_info(d.screen().root)
            # msSinceLastInput is the field in XScreenSaverQueryInfo
            return float(info.idle) / 1000.0
        except Exception as e:
            logger.error("linux_get_idle_time_failed", error=str(e))
            return 0.0
