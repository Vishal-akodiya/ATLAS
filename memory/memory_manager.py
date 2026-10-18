import os
import re
import json
import threading
from datetime import datetime
from typing import List, Dict, Any, Callable, Optional
from memory.config_manager import WORKSPACE_DIR

TASKS_FILE = os.path.join(WORKSPACE_DIR, "tasks.json")
MEMORY_FILE = os.path.join(WORKSPACE_DIR, "memory.json")
AUDIT_LOG_FILE = os.path.join(WORKSPACE_DIR, "audit.log")

SECRET_PATTERNS = re.compile(
    r"(password|passwd|secret|api[_\-]?key|token|bearer|private[_\-]?key|ssn|credit[_\-]?card)",
    re.IGNORECASE,
)


class MemoryManager:
    def __init__(
        self,
        on_tasks_updated: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
        on_memories_updated: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.on_tasks_updated = on_tasks_updated
        self.on_memories_updated = on_memories_updated
        # Shared by reminder actions and the scheduler so simultaneous task updates
        # cannot overwrite one another or leave a partially-written JSON file.
        self.tasks_lock = threading.RLock()
        self._ensure_memory_structure()

    def _ensure_memory_structure(self):
        if not os.path.exists(MEMORY_FILE):
            initial = {
                "profile": {},
                "workspace": {},
                "task_state": {
                    "objective": "",
                    "completed_steps": [],
                    "resume_point": "",
                    "updated_at": ""
                },
                "episodic": []
            }
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(initial, f, indent=4)

    def log_audit(self, tool_name: str, level: int, status: str, details: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] [L{level}] {tool_name} -> {status} | {details}\n"
        try:
            with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass

    def read_recent_logs(self, lines: int = 25) -> str:
        if not os.path.exists(AUDIT_LOG_FILE):
            return "No audit logs recorded yet."
        try:
            with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
            return "".join(all_lines[-lines:])
        except Exception as e:
            return f"Error reading logs: {e}"

    # --- 4-Tier Memory CRUD ---
    def load_all_memories(self) -> Dict[str, Any]:
        self._ensure_memory_structure()
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k in ("profile", "workspace", "task_state", "episodic"):
                if k not in data:
                    data[k] = {} if k != "episodic" else []
            return data
        except Exception:
            return {"profile": {}, "workspace": {}, "task_state": {}, "episodic": []}

    def _save_all_memories(self, data: Dict[str, Any]):
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        if self.on_memories_updated:
            self.on_memories_updated(data)

    def save_memory(self, category: str, key: str, value: str, provenance: str = "user_explicit") -> tuple[bool, str]:
        """Saves a memory to 'profile' or 'workspace' after checking for sensitive secrets."""
        if SECRET_PATTERNS.search(key) or SECRET_PATTERNS.search(value):
            return False, "BLOCKED: Memory contains restricted sensitive keywords (passwords/keys/tokens)."

        cat = category.strip().lower()
        if cat not in ("profile", "workspace"):
            cat = "workspace"

        data = self.load_all_memories()
        norm_key = key.strip().lower()
        data[cat][norm_key] = {
            "value": value.strip(),
            "provenance": provenance,
            "confidence": "high",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        self._save_all_memories(data)
        return True, f"VERIFIED: Saved [{cat}] '{norm_key}' = '{value.strip()}'"

    def delete_memory(self, category: str, key: str) -> bool:
        data = self.load_all_memories()
        cat = category.strip().lower()
        norm_key = key.strip().lower()
        if cat in ("profile", "workspace") and norm_key in data[cat]:
            del data[cat][norm_key]
            self._save_all_memories(data)
            return True
        # Search both if category wasn't specified accurately
        for c in ("profile", "workspace"):
            if norm_key in data[c]:
                del data[c][norm_key]
                self._save_all_memories(data)
                return True
        return False

    def update_task_checkpoint(self, objective: str, completed_step: str, resume_point: str):
        data = self.load_all_memories()
        ts = data.get("task_state", {})
        steps = ts.get("completed_steps", [])
        if completed_step:
            steps.append(f"{datetime.now().strftime('%H:%M')} - {completed_step}")
        data["task_state"] = {
            "objective": objective,
            "completed_steps": steps[-10:],
            "resume_point": resume_point,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        self._save_all_memories(data)

    def add_episodic_summary(self, summary: str):
        data = self.load_all_memories()
        episodes = data.get("episodic", [])
        episodes.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "summary": summary
        })
        data["episodic"] = episodes[-20:]
        self._save_all_memories(data)

    # --- Durable Tasks & Reminders ---
    def load_tasks(self) -> List[Dict[str, Any]]:
        with self.tasks_lock:
            if not os.path.exists(TASKS_FILE):
                return []
            try:
                with open(TASKS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data if isinstance(data, list) else []
            except (OSError, json.JSONDecodeError, TypeError):
                # Atomic writes prevent new partial files; this fallback keeps the
                # assistant operational if an old/corrupt file is encountered.
                return []

    def save_tasks(self, tasks: List[Dict[str, Any]]):
        os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
        active = [
            dict(task) for task in tasks
            if task.get("status", "pending") == "pending" and not task.get("notified")
        ]
        with self.tasks_lock:
            tmp_path = TASKS_FILE + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(tasks, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, TASKS_FILE)
        if self.on_tasks_updated:
            try:
                self.on_tasks_updated(active)
            except Exception as exc:
                print(f"[Tasks] UI refresh failed: {exc}")

    def get_active_tasks(self) -> List[Dict[str, Any]]:
        return [
            task for task in self.load_tasks()
            if task.get("status", "pending") == "pending" and not task.get("notified")
        ]
