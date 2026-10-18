import os
import shutil
from datetime import datetime
from typing import List, Dict, Any
from memory.config_manager import WORKSPACE_DIR
from typing import List, Dict, Any, Optional

BACKUP_DIR = os.path.join(WORKSPACE_DIR, ".backups")
os.makedirs(BACKUP_DIR, exist_ok=True)


class UndoManager:
    def __init__(self):
        self.history: List[Dict[str, Any]] = []

    def backup_file(self, filepath: str, operation: str, target_path: Optional[str] = None) -> str:
        """Creates a timestamped backup copy of a file before overwriting, moving, or deleting."""
        if not os.path.exists(filepath):
            return ""
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.basename(filepath)
        backup_path = os.path.join(BACKUP_DIR, f"{stamp}_{base}")
        shutil.copy2(filepath, backup_path)
        self.history.append({
            "type": "file_restore",
            "operation": operation,
            "original_path": filepath,
            "target_path": target_path,
            "backup_path": backup_path,
            "timestamp": stamp,
        })
        return backup_path

    def record_created_file(self, filepath: str):
        self.history.append({
            "type": "file_created",
            "operation": "create_file",
            "original_path": filepath,
            "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        })

    def undo_last(self) -> str:
        if not self.history:
            return "No reversible actions in undo history."
        last = self.history.pop()
        try:
            if last["type"] == "file_restore":
                shutil.copy2(last["backup_path"], last["original_path"])
                if last.get("operation") == "move_file" and last.get("target_path"):
                    if os.path.exists(last["target_path"]) and last["target_path"] != last["original_path"]:
                        os.remove(last["target_path"])
                return f"VERIFIED UNDO: Restored '{os.path.basename(last['original_path'])}' ({last['operation']})."
            elif last["type"] == "file_created":
                if os.path.exists(last["original_path"]):
                    os.remove(last["original_path"])
                return f"VERIFIED UNDO: Removed newly created file '{os.path.basename(last['original_path'])}'."
        except Exception as e:
            return f"FAILED UNDO: {e}"
        return "Nothing to undo."