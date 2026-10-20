import os
import glob
import json
import time
import shutil
import ctypes
import difflib
import subprocess
import threading
import psutil
import pyautogui
from typing import Callable, Optional, Dict
from memory.config_manager import ConfigManager
from memory.memory_manager import MemoryManager
from core.confirm import ConfirmationGate

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.04

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

RESTRICTED_HOTKEYS = {
    "alt+f4",
    "ctrl+shift+esc",
    "ctrl+alt+del",
    "ctrl+alt+delete",
    "win+r",
    "win+x",
    "ctrl+shift+del",
}


class DesktopActions:
    def __init__(
        self,
        config: ConfigManager,
        memory: MemoryManager,
        confirm: ConfirmationGate,
        on_action_status: Optional[Callable[[str], None]] = None,
    ):
        self.config = config
        self.memory = memory
        self.confirm = confirm
        self.on_action_status = on_action_status
        self.emergency_stop_event = threading.Event()
        self.screen_processor = None

        self.installed_apps: Dict[str, Dict[str, str]] = {}
        threading.Thread(target=self._index_installed_apps, daemon=True).start()

    def bind_screen_processor(self, screen_processor):
        self.screen_processor = screen_processor

    def _notify(self, text: str):
        if self.on_action_status:
            self.on_action_status(text)

    def trigger_emergency_stop(self):
        self.emergency_stop_event.set()
        self.memory.log_audit("emergency_stop", 0, "TRIGGERED", "All automation halted.")

    def clear_emergency_stop(self):
        self.emergency_stop_event.clear()

    # ==========================================
    # ROBUST THREAD-SAFE CLIPBOARD INJECTION
    # ==========================================
    @staticmethod
    def _paste_via_clipboard(text: str):
        """Thread-safe clipboard injection using native Windows ctypes (avoids Tkinter crashes)."""
        try:
            CF_UNICODETEXT = 13
            user32.OpenClipboard(0)
            user32.EmptyClipboard()
            
            text_bytes = text.encode("utf-16le") + b"\0\0"
            hGlobalMem = kernel32.GlobalAlloc(0x0042, len(text_bytes))
            pGlobalMem = kernel32.GlobalLock(hGlobalMem)
            
            ctypes.memmove(pGlobalMem, text_bytes, len(text_bytes))
            kernel32.GlobalUnlock(hGlobalMem)
            
            user32.SetClipboardData(CF_UNICODETEXT, hGlobalMem)
            user32.CloseClipboard()

            time.sleep(0.12)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.12)
        except Exception:
            # Fallback to standard typing if clipboard API is locked by another app
            pyautogui.write(text, interval=0.015)

    # ==========================================
    # WINDOW FOCUSING & APP LAUNCHER
    # ==========================================
    def list_open_windows(self) -> str:
        """Lists all currently visible application windows on the desktop so you can focus the right window or decide if an app needs to be launched."""
        titles = []

        def enum_cb(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value.strip()
                    if title and title not in titles:
                        titles.append(title)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        if not titles:
            return "No visible application windows found."
        return "Open Windows:\n" + "\n".join(f"- {t}" for t in titles[:35])

    def focus_window(self, title_substring: str) -> str:
        """Brings an already-open application window matching title_substring to the foreground."""
        matched_hwnd = []

        def enum_cb(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    if title_substring.lower() in buf.value.lower():
                        matched_hwnd.append((hwnd, buf.value))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

        if not matched_hwnd:
            return f"FAILED: No visible window found matching '{title_substring}'."

        hwnd, full_title = matched_hwnd[0]

        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)
        else:
            user32.ShowWindow(hwnd, 5)

        foreground_hwnd = user32.GetForegroundWindow()
        cur_thread_id = kernel32.GetCurrentThreadId()
        fore_thread_id = user32.GetWindowThreadProcessId(foreground_hwnd, None)
        target_thread_id = user32.GetWindowThreadProcessId(hwnd, None)

        if fore_thread_id != cur_thread_id:
            user32.AttachThreadInput(cur_thread_id, fore_thread_id, True)
        if target_thread_id != cur_thread_id:
            user32.AttachThreadInput(cur_thread_id, target_thread_id, True)

        user32.keybd_event(0x12, 0, 0, 0)
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        user32.keybd_event(0x12, 0, 2, 0)

        if fore_thread_id != cur_thread_id:
            user32.AttachThreadInput(cur_thread_id, fore_thread_id, False)
        if target_thread_id != cur_thread_id:
            user32.AttachThreadInput(cur_thread_id, target_thread_id, False)

        time.sleep(0.3)
        self.memory.log_audit("focus_window", 1, "VERIFIED", full_title)
        return f"VERIFIED: Brought window '{full_title}' to the front."

    def _index_installed_apps(self):
        apps: Dict[str, Dict[str, str]] = {}
        for k, v in self.config.get("allowed_apps", {}).items():
            apps[k.lower()] = {"name": k, "type": "cmd", "target": v}

        try:
            ps_cmd = "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress"
            proc = subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_cmd], capture_output=True, text=True, timeout=8)
            if proc.stdout:
                items = json.loads(proc.stdout)
                if isinstance(items, dict): items = [items]
                for item in items:
                    name = (item.get("Name") or "").strip()
                    appid = (item.get("AppID") or "").strip()
                    if name and appid: apps[name.lower()] = {"name": name, "type": "shell_app", "target": appid}
        except Exception:
            pass

        shortcut_dirs = [
            os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expanduser(r"~\Desktop"),
        ]
        for sdir in shortcut_dirs:
            if os.path.exists(sdir):
                for lnk in glob.glob(os.path.join(sdir, "**", "*.lnk"), recursive=True):
                    base = os.path.splitext(os.path.basename(lnk))[0].strip()
                    if base.lower() not in apps: apps[base.lower()] = {"name": base, "type": "lnk", "target": lnk}

        self.installed_apps = apps

    def list_installed_apps(self, search_filter: str = "") -> str:
        """Searches installed desktop and Microsoft Store applications matching search_filter."""
        if not self.installed_apps:
            self._index_installed_apps()
        names = sorted({info["name"] for info in self.installed_apps.values()})
        if search_filter:
            names = [n for n in names if search_filter.lower() in n.lower()]
        if not names:
            return f"No apps found matching '{search_filter}'."
        return f"Found {len(names)} installed apps: {', '.join(names[:40])}"

    def open_app(self, app_name: str) -> str:
        """Finds and launches any installed application by name (e.g., Spotify, Discord, Notepad, Chrome, WhatsApp, VS Code) and brings its window to the front."""
        query = app_name.strip().lower()
        if not query: return "FAILED: App name is empty."
        if not self.installed_apps: self._index_installed_apps()

        self._notify(f"🚀 Opening '{app_name}'...")
        match_info = self.installed_apps.get(query)
        if not match_info:
            for key, info in self.installed_apps.items():
                if query in key or key in query:
                    match_info = info
                    break
        if not match_info:
            close = difflib.get_close_matches(query, list(self.installed_apps.keys()), n=1, cutoff=0.68)
            if close: match_info = self.installed_apps[close[0]]

        try:
            if match_info:
                ltype = match_info["type"]
                target = match_info["target"]
                disp_name = match_info["name"]
                if ltype == "shell_app": subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{target}"])
                elif ltype == "lnk": os.startfile(target)
                else: subprocess.Popen(target, shell=True)
                time.sleep(1.2)
                self.focus_window(disp_name)
                return f"VERIFIED: Launched '{disp_name}'."

            which_path = shutil.which(query) or shutil.which(f"{query}.exe")
            if which_path:
                subprocess.Popen([which_path])
                time.sleep(1.0)
                self.focus_window(app_name)
                return f"VERIFIED: Launched '{app_name}'."

            pyautogui.hotkey("win", "s")
            time.sleep(0.4)
            self._paste_via_clipboard(app_name)
            time.sleep(0.4)
            pyautogui.press("enter")
            time.sleep(1.5)
            self.focus_window(app_name)
            return f"VERIFIED: Opened '{app_name}' via Windows search."
        except Exception as e:
            return f"FAILED to open '{app_name}': {e}"

    def type_text(self, text: str, press_enter: bool = False) -> str:
        """Types or pastes text into the currently focused input field, optionally pressing Enter afterward."""
        if self.emergency_stop_event.is_set():
            return "STOPPED."
        self._notify(f"Entering text: '{text[:30]}'...")
        self._paste_via_clipboard(text)
        if press_enter:
            time.sleep(0.1)
            pyautogui.press("enter")
        return f"VERIFIED: Entered '{text}'"
    
    def minimize_window(self, title_substring: str) -> str:
        """Minimizes a visible window matching title_substring."""
        matched_hwnd = []

        def enum_cb(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    if title_substring.lower() in buf.value.lower():
                        matched_hwnd.append((hwnd, buf.value))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        if not matched_hwnd:
            return f"FAILED: No visible window found matching '{title_substring}'."

        hwnd, full_title = matched_hwnd[0]
        user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE = 6
        self.memory.log_audit("minimize_window", 1, "VERIFIED", full_title)
        return f"VERIFIED: Minimized window '{full_title}'."

    def press_hotkey(self, keys_csv: str) -> str:
        """Presses a keyboard key or shortcut combination (e.g., 'ctrl+f', 'ctrl+n', 'enter', 'tab', 'space')."""
        if self.emergency_stop_event.is_set(): return "STOPPED."
        keys = [k.strip().lower() for k in keys_csv.replace("+", ",").split(",") if k.strip()]
        self._notify(f"⌨️ Shortcut: {'+'.join(keys).upper()}")
        
        combo = "+".join(keys)
        if combo in RESTRICTED_HOTKEYS:
            appr, rsn = self.confirm.request_approval("System Shortcut", combo.upper(), "System", "May close app", 2)
            if not appr: return f"CANCELLED: {rsn}"
            
        if len(keys) == 1: pyautogui.press(keys[0])
        else: pyautogui.hotkey(*keys)
        return f"VERIFIED: Pressed {'+'.join(keys)}."

    def click_control(self, x: int, y: int, button: str = "left", double: bool = False) -> str:
        """Clicks specific screen pixel coordinates (x, y)."""
        if self.emergency_stop_event.is_set(): return "STOPPED."
        pyautogui.moveTo(int(x), int(y), duration=0.2)
        if double: pyautogui.doubleClick(x=int(x), y=int(y), button=button)
        else: pyautogui.click(x=int(x), y=int(y), button=button)
        return f"VERIFIED: Clicked ({x}, {y})."

    def scroll_screen(self, direction: str = "down", clicks: int = 5) -> str:
        """Scrolls the active window 'up' or 'down'."""
        amt = -abs(int(clicks)) * 120 if direction.lower() == "down" else abs(int(clicks)) * 120
        pyautogui.scroll(amt)
        return f"VERIFIED: Scrolled {direction}."

    def close_app(self, process_name: str) -> str:
        """Closes/terminates a running application process after user confirmation."""
        appr, rsn = self.confirm.request_approval("Close Application", process_name, "Active Processes", "Data may be lost", 2)
        if not appr: return f"CANCELLED: {rsn}"
        for proc in psutil.process_iter(["name"]):
            try:
                if process_name.lower() in (proc.info["name"] or "").lower(): proc.terminate()
            except Exception: pass
        return f"VERIFIED: Closed '{process_name}'."