import os
import json
from datetime import datetime

WORKSPACE_DIR = os.path.join(os.getcwd(), "ATLAS_Workspace")
CONFIG_FILE = os.path.join(WORKSPACE_DIR, "config.json")
os.makedirs(WORKSPACE_DIR, exist_ok=True)

DEFAULT_CONFIG = {
    "wake_word_enabled": True,
    "quiet_mode": False,
    "quiet_hours_start": "23:00",
    "quiet_hours_end": "07:00",
    "store_raw_audio": False,
    "deadline_nudge_minutes": 15,
    "allowed_apps": {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "browser": "start msedge",
        "explorer": "explorer.exe",
        "paint": "mspaint.exe",
        "cmd": "start cmd"
    },
    "allowed_commands": [
        "ipconfig",
        "whoami",
        "hostname",
        "systeminfo",
        "tasklist",
        "dir"
    ]
}


class ConfigManager:
    def __init__(self):
        self.config = self._load()

    def _load(self) -> dict:
        if not os.path.exists(CONFIG_FILE):
            self._save(DEFAULT_CONFIG)
            return dict(DEFAULT_CONFIG)
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = dict(DEFAULT_CONFIG)
            merged.update(data)
            return merged
        except Exception:
            return dict(DEFAULT_CONFIG)

    def _save(self, data: dict):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def set(self, key: str, value):
        self.config[key] = value
        self._save(self.config)

    def is_quiet_hours(self) -> bool:
        if self.config.get("quiet_mode", False):
            return True
        try:
            now = datetime.now().strftime("%H:%M")
            start = self.config.get("quiet_hours_start", "23:00")
            end = self.config.get("quiet_hours_end", "07:00")
            if start <= end:
                return start <= now <= end
            return now >= start or now <= end
        except Exception:
            return False