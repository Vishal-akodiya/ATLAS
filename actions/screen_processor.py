import os
import re
import json
import time
import ctypes
import mss
import pyautogui
from PIL import Image
from memory.config_manager import WORKSPACE_DIR
from memory.memory_manager import MemoryManager

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class ScreenProcessor:
    def __init__(
        self,
        memory: MemoryManager,
        desktop_actions,
        gemini_engine=None,
        on_preview_Callback=None,
        on_action_status=None,
    ):
        self.memory = memory
        self.desktop = desktop_actions
        self.gemini = gemini_engine
        self.on_preview = on_preview_Callback
        self.on_action_status = on_action_status
        self.hide_ui_cb = None
        self.show_ui_cb = None

    def bind_gemini(self, gemini_engine):
        self.gemini = gemini_engine

    def bind_window_controls(self, hide_cb, show_cb):
        self.hide_ui_cb = hide_cb
        self.show_ui_cb = show_cb

    def capture_raw_screen(self, hide_atlas: bool = True) -> tuple[str, int, int]:
        if hide_atlas and self.hide_ui_cb:
            self.hide_ui_cb()
            time.sleep(0.12)

        out_path = os.path.join(WORKSPACE_DIR, "current_screen.jpg")
        with mss.mss() as sct:
            sct_img = sct.grab(sct.monitors[1])
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            img.save(out_path, format="JPEG", quality=85)

        if hide_atlas and self.show_ui_cb:
            self.show_ui_cb()

        screen_w, screen_h = pyautogui.size()
        if self.on_preview:
            self.on_preview(out_path)
        return out_path, screen_w, screen_h

    def _locate_element_coords(self, target_description: str) -> tuple[int, int] | None:
        img_path, screen_w, screen_h = self.capture_raw_screen(hide_atlas=True)
        img = Image.open(img_path)

        prompt = (
            f"You are a computer vision agent. Locate this UI element on the screen: '{target_description}'.\n"
            f"Return ONLY a JSON object: {{\"found\": true, \"x_norm\": 500, \"y_norm\": 500}}\n"
            f"x_norm and y_norm must be integers from 0 to 1000 representing the center of the element."
        )

        try:
            raw = self.gemini.generate_vision_content(prompt, img, temperature=0.0)
            match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            if not match:
                return None
            data = json.loads(match.group(0))
            if not data.get("found"):
                return None

            x_norm = max(0, min(1000, int(data.get("x_norm", 500))))
            y_norm = max(0, min(1000, int(data.get("y_norm", 500))))
            px = int((x_norm / 1000.0) * screen_w)
            py = int((y_norm / 1000.0) * screen_h)
            return px, py
        except Exception:
            return None

    def inspect_screen_state(self, question_or_goal: str = "Describe active windows and interactive controls.") -> str:
        """Captures a live screenshot and analyzes the active application window, UI layout, text fields, and buttons to determine the next action for the user's goal."""
        if self.on_action_status:
            self.on_action_status("Analyzing screen...")
        img_path, screen_w, screen_h = self.capture_raw_screen(hide_atlas=True)
        img = Image.open(img_path)
        prompt = f"Screenshot ({screen_w}x{screen_h}). Goal: {question_or_goal}\nIdentify active window, controls, and dialogs."
        summary = self.gemini.generate_vision_content(prompt, img, temperature=0.1)
        self.memory.log_audit("inspect_screen", 0, "VERIFIED", question_or_goal[:40])
        return f"VERIFIED Screen Analysis:\n{summary}"

    def locate_and_interact_on_screen(
        self,
        element_description: str,
        interaction_type: str = "click",
        text_to_type: str = "",
        press_enter: bool = False,
    ) -> str:
        """Visually locates any UI element on the current screen (e.g., search bar, contact row, play button, text input box) and interacts with it.
        interaction_type: 'click', 'double_click', 'right_click', or 'move_only'.
        text_to_type: Optional text to paste/type after clicking the element.
        press_enter: Set True to press Enter after clicking or typing."""
        if self.desktop.emergency_stop_event.is_set():
            return "STOPPED."
        if self.on_action_status:
            self.on_action_status(f"Locating: '{element_description}'...")
        coords = self._locate_element_coords(element_description)
        if not coords:
            return f"FAILED: Could not find '{element_description}'."
        tx, ty = coords
        if self.hide_ui_cb:
            self.hide_ui_cb()
            time.sleep(0.08)
        try:
            pyautogui.moveTo(tx, ty, duration=0.18)
            itype = interaction_type.strip().lower()
            if itype == "double_click":
                pyautogui.doubleClick(tx, ty)
            elif itype == "right_click":
                pyautogui.rightClick(tx, ty)
            elif itype != "move_only":
                pyautogui.click(tx, ty)
            if text_to_type:
                time.sleep(0.2)
                self.desktop._paste_via_clipboard(text_to_type)
                if press_enter:
                    time.sleep(0.1)
                    pyautogui.press("enter")
            elif press_enter:
                time.sleep(0.1)
                pyautogui.press("enter")
        finally:
            time.sleep(0.1)
            if self.show_ui_cb:
                self.show_ui_cb()
        self.memory.log_audit("interact", 1, "VERIFIED", f"{interaction_type} @ ({tx},{ty})")
        return f"VERIFIED: Interacted with '{element_description}' at ({tx}, {ty})."