"""FL Studio trigger utility for script execution.

This module handles sending keystrokes to FL Studio to trigger scripts:
- Piano Roll script (ComposeWithLLM.pyscript) via Ctrl+Alt+Y
- Control Plane script (ControlPlane.pyscript) via Ctrl+Alt+M
"""

from __future__ import annotations

import platform
import subprocess
import time
from typing import Callable

# Delay after triggering to allow FL Studio to process
TRIGGER_DELAY = 2.0


class FLStudioTrigger:
    """Handles triggering FL Studio scripts via keystrokes."""

    def __init__(self) -> None:
        self._system = platform.system()
        self._trigger_func_piano_roll: Callable[[], bool] | None = None
        self._trigger_func_control_plane: Callable[[], bool] | None = None
        self._setup_triggers()

    def _setup_triggers(self) -> None:
        """Set up the appropriate trigger methods for the current platform."""
        if self._system == "Darwin":
            self._trigger_func_piano_roll = lambda: self._trigger_macos("y")
            self._trigger_func_control_plane = lambda: self._trigger_macos("m")
        elif self._system == "Windows":
            self._trigger_func_piano_roll = lambda: self._trigger_windows("y")
            self._trigger_func_control_plane = lambda: self._trigger_windows("m")
        else:
            self._trigger_func_piano_roll = None
            self._trigger_func_control_plane = None

    def _trigger_macos(self, key: str) -> bool:
        """Trigger FL Studio on macOS using osascript."""
        try:
            # Use osascript to send keystroke to FL Studio
            script = f'''
            tell application "FL Studio"
                activate
            end tell
            delay 0.3
            tell application "System Events"
                keystroke "{key}" using {{command down, option down}}
            end tell
            '''
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=10,
            )
            return True
        except subprocess.TimeoutExpired:
            return False
        except Exception:
            # Fallback to pynput
            return self._trigger_macos_pynput(key)

    def _trigger_macos_pynput(self, key: str) -> bool:
        """Trigger FL Studio on macOS using pynput."""
        try:
            from pynput.keyboard import Controller, Key

            keyboard = Controller()

            # Focus FL Studio first
            subprocess.run(
                ["osascript", "-e", 'tell application "FL Studio" to activate'],
                capture_output=True,
                timeout=5,
            )
            time.sleep(0.3)

            # Send Cmd+Opt+Key
            keyboard.press(Key.cmd)
            keyboard.press(Key.alt)
            keyboard.press(key)
            keyboard.release(key)
            keyboard.release(Key.alt)
            keyboard.release(Key.cmd)

            return True
        except Exception:
            return False

    def _focus_fl_studio_windows(self) -> bool:
        """Bring the FL Studio window to the foreground on Windows.

        The keystroke that triggers the script is delivered to
        whichever window has focus, so FL Studio must be foregrounded first
        (mirroring the ``activate`` step used on macOS). Uses only ctypes/user32
        so no extra dependency is required.

        Returns:
            True if an FL Studio window was found and foregrounded, else False.
        """
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32

            found = {"hwnd": None}

            EnumWindowsProc = ctypes.WINFUNCTYPE(
                ctypes.c_bool, wintypes.HWND, wintypes.LPARAM
            )

            def _enum(hwnd, _lparam):
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length == 0:
                    return True
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                # FL Studio's main window title contains "FL Studio" (e.g., "FL Studio 2025")
                if "FL Studio" in buffer.value:
                    found["hwnd"] = hwnd
                    return False  # stop enumerating
                return True

            user32.EnumWindows(EnumWindowsProc(_enum), 0)

            hwnd = found["hwnd"]
            if not hwnd:
                return False

            # Restore if minimized, then foreground it.
            SW_RESTORE = 9
            user32.ShowWindow(hwnd, SW_RESTORE)

            # Windows normally forbids a background process from stealing focus.
            # Tapping ALT unlocks SetForegroundWindow for this call.
            VK_MENU = 0x12
            KEYEVENTF_KEYUP = 0x0002
            user32.keybd_event(VK_MENU, 0, 0, 0)
            user32.SetForegroundWindow(hwnd)
            user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)

            return True
        except Exception:
            return False

    def _trigger_windows(self, key: str) -> bool:
        """Trigger FL Studio on Windows using pynput.

        Foregrounds FL Studio first so the Ctrl+Alt+Key hotkey actually reaches
        it; returns False (so the caller reports a manual-trigger warning) if the
        FL Studio window can't be found.
        """
        try:
            from pynput.keyboard import Controller, Key

            if not self._focus_fl_studio_windows():
                return False

            # Give FL Studio a moment to accept focus before the keystroke.
            time.sleep(0.3)

            keyboard = Controller()

            # Send Ctrl+Alt+Key
            keyboard.press(Key.ctrl)
            keyboard.press(Key.alt)
            keyboard.press(key)
            keyboard.release(key)
            keyboard.release(Key.alt)
            keyboard.release(Key.ctrl)

            return True
        except Exception:
            return False

    def trigger_piano_roll(self, delay: float = TRIGGER_DELAY) -> bool:
        """Trigger FL Studio to execute the Piano Roll script (Ctrl+Alt+Y)."""
        if self._trigger_func_piano_roll is None:
            return False

        success = self._trigger_func_piano_roll()
        if success and delay > 0:
            time.sleep(delay)

        return success

    def trigger_control_plane(self, delay: float = TRIGGER_DELAY) -> bool:
        """Trigger FL Studio to execute the Control Plane script (Ctrl+Alt+M)."""
        if self._trigger_func_control_plane is None:
            return False

        success = self._trigger_func_control_plane()
        if success and delay > 0:
            time.sleep(delay)

        return success

    @property
    def is_supported(self) -> bool:
        """Check if triggering is supported on this platform."""
        return self._trigger_func_piano_roll is not None

    @property
    def platform(self) -> str:
        """Get the current platform name."""
        return self._system

    @property
    def piano_roll_keystroke(self) -> str:
        """Get the keystroke used for piano roll on this platform."""
        if self._system == "Darwin":
            return "Cmd+Opt+Y"
        elif self._system == "Windows":
            return "Ctrl+Alt+Y"
        return "Unknown"

    @property
    def control_plane_keystroke(self) -> str:
        """Get the keystroke used for control plane on this platform."""
        if self._system == "Darwin":
            return "Cmd+Opt+M"
        elif self._system == "Windows":
            return "Ctrl+Alt+M"
        return "Unknown"


# Global trigger instance
_trigger: FLStudioTrigger | None = None


def get_trigger() -> FLStudioTrigger:
    """Get the global FL Studio trigger instance."""
    global _trigger
    if _trigger is None:
        _trigger = FLStudioTrigger()
    return _trigger


def trigger_fl_studio(delay: float = TRIGGER_DELAY) -> bool:
    """Convenience function to trigger FL Studio Piano Roll script.

    Args:
        delay: Seconds to wait after triggering.

    Returns:
        True if successful, False otherwise.
    """
    return get_trigger().trigger_piano_roll(delay)


def trigger_control_plane(delay: float = TRIGGER_DELAY) -> bool:
    """Convenience function to trigger FL Studio Control Plane script.

    Args:
        delay: Seconds to wait after triggering.

    Returns:
        True if successful, False otherwise.
    """
    return get_trigger().trigger_control_plane(delay)
