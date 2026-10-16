import os
import re
import json
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime
import psutil
from memory.memory_manager import MemoryManager, WORKSPACE_DIR
from core.confirm import ConfirmationGate


class ToolRegistry:
    def __init__(self, memory: MemoryManager, confirm_gate: ConfirmationGate):
        self.memory = memory
        self.confirm = confirm_gate

    def get_tools_list(self):
        return [
            self.create_note,
            self.read_document,
            self.search_files,
            self.delete_file,
            self.open_application,
            self.get_current_time,
            self.create_task,
            self.list_tasks,
            self.cancel_task,
            self.save_memory,
            self.recall_memories,
            self.delete_memory,
            self.search_wikipedia,
            self.check_system_status,
        ]

    # --- Level 0: Read-Only Tools ---
    def get_current_time(self) -> str:
        """Returns the current local date and 24-hour time."""
        now_str = datetime.now().strftime("%A, %B %d, %Y - %H:%M")
        self.memory.log_audit("get_current_time", 0, "SUCCESS", now_str)
        return now_str

    def read_document(self, filename: str) -> str:
        """Reads a text or markdown file inside ATLAS_Workspace."""
        safe_name = os.path.basename(filename)
        filepath = os.path.join(WORKSPACE_DIR, safe_name)
        if not os.path.exists(filepath):
            self.memory.log_audit("read_document", 0, "FAILED", f"Missing: {safe_name}")
            return f"FAILED: File '{safe_name}' does not exist in workspace."
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            self.memory.log_audit("read_document", 0, "SUCCESS", safe_name)
            return f"SUCCESS (Source: {safe_name}):\n{content}"
        except Exception as e:
            return f"FAILED: Error reading file - {e}"

    def search_files(self, keyword: str) -> str:
        """Searches for files matching keyword in ATLAS_Workspace."""
        files = os.listdir(WORKSPACE_DIR)
        matches = [
            f for f in files
            if keyword.lower() in f.lower() and os.path.isfile(os.path.join(WORKSPACE_DIR, f))
        ]
        self.memory.log_audit("search_files", 0, "SUCCESS", f"Query='{keyword}', Matches={len(matches)}")
        if not matches:
            return f"No files found matching '{keyword}'."
        return f"Found files: {', '.join(matches)}"

    def search_wikipedia(self, query: str) -> str:
        """Searches Wikipedia and returns a verified summary with source title."""
        try:
            safe_query = urllib.parse.quote(query)
            url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={safe_query}&utf8=&format=json"
            req = urllib.request.Request(url, headers={"User-Agent": "ATLAS_AI/2.0"})
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode())
                results = data.get("query", {}).get("search", [])
                if not results:
                    return f"No Wikipedia results found for '{query}'."
                title = results[0]["title"]
                clean_snippet = re.sub(r"<[^>]+>", "", results[0]["snippet"])
                checked_date = datetime.now().strftime("%Y-%m-%d")
                self.memory.log_audit("search_wikipedia", 0, "SUCCESS", title)
                return f"Source: Wikipedia ({title}) [Checked: {checked_date}]\nSummary: {clean_snippet}..."
        except Exception as e:
            return f"FAILED: Web search error - {e}"

    def check_system_status(self) -> str:
        """Returns CPU, RAM, and free disk space diagnostics."""
        cpu = psutil.cpu_percent(interval=0.2)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage(os.getcwd())
        free_gb = round(disk.free / (1024 ** 3), 2)
        status = f"CPU Usage: {cpu}%, RAM Usage: {ram}%, Free Disk Space: {free_gb} GB"
        self.memory.log_audit("check_system_status", 0, "SUCCESS", status)
        return status

    # --- Level 1: Reversible Local Tools ---
    def create_note(self, filename: str, content: str) -> str:
        """Creates or updates a note in ATLAS_Workspace. Requests approval if overwriting."""
        safe_filename = "".join([c for c in filename if c.isalnum() or c in " ._-"]).rstrip()
        if not safe_filename:
            return "FAILED: Invalid filename."
        if not safe_filename.endswith((".txt", ".md")):
            safe_filename += ".md"

        filepath = os.path.join(WORKSPACE_DIR, safe_filename)
        if os.path.exists(filepath):
            approved = self.confirm.request_approval(
                "Overwrite Existing Note",
                f"Target: {safe_filename}",
                risk_level=2
            )
            if not approved:
                self.memory.log_audit("create_note", 2, "DENIED", safe_filename)
                return f"CANCELLED: User denied overwriting '{safe_filename}'."

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            # Verification step: confirm file exists and is non-empty if content was supplied
            if os.path.exists(filepath) and (os.path.getsize(filepath) > 0 or len(content) == 0):
                self.memory.log_audit("create_note", 1, "VERIFIED", safe_filename)
                return f"SUCCESS: Verified note saved at {filepath}"
            return "FAILED: File could not be verified after write."
        except Exception as e:
            return f"FAILED: Error saving note - {e}"

    def open_application(self, app_name: str) -> str:
        """Launches an allowlisted desktop application (notepad, calculator, browser, explorer)."""
        allowed_apps = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "browser": "start msedge",
            "explorer": "explorer.exe"
        }
        key = app_name.strip().lower()
        if key not in allowed_apps:
            self.memory.log_audit("open_application", 1, "BLOCKED", key)
            return f"FAILED: '{app_name}' is not in the approved application allowlist."
        try:
            subprocess.Popen(allowed_apps[key], shell=True)
            self.memory.log_audit("open_application", 1, "SUCCESS", key)
            return f"SUCCESS: Launched {app_name}."
        except Exception as e:
            return f"FAILED: {e}"

    def create_task(self, title: str, due_time_str: str) -> str:
        """Schedules a reminder task. due_time_str MUST be in 'YYYY-MM-DD HH:MM' format."""
        try:
            datetime.strptime(due_time_str, "%Y-%m-%d %H:%M")
            tasks = self.memory.load_tasks()
            task_id = max([t["id"] for t in tasks] + [0]) + 1
            new_task = {"id": task_id, "title": title, "due_time": due_time_str, "notified": False}
            tasks.append(new_task)
            self.memory.save_tasks(tasks)
            self.memory.log_audit("create_task", 1, "VERIFIED", f"#{task_id} {title} @ {due_time_str}")
            return f"SUCCESS: Verified Task #{task_id} ('{title}') scheduled for {due_time_str}."
        except ValueError:
            return "FAILED: Invalid time format. Must be 'YYYY-MM-DD HH:MM'."

    def list_tasks(self) -> str:
        """Lists all active pending tasks and reminders."""
        tasks = self.memory.get_active_tasks()
        if not tasks:
            return "No pending tasks."
        return "\n".join([f"ID {t['id']}: {t['title']} (Due: {t['due_time']})" for t in tasks])

    def cancel_task(self, task_id: int) -> str:
        """Marks a task ID as completed/cancelled."""
        tasks = self.memory.load_tasks()
        for t in tasks:
            if t["id"] == int(task_id):
                t["notified"] = True
                self.memory.save_tasks(tasks)
                self.memory.log_audit("cancel_task", 1, "VERIFIED", f"ID {task_id}")
                return f"SUCCESS: Task #{task_id} completed/cancelled."
        return f"FAILED: Task ID {task_id} not found."

    def save_memory(self, key: str, value: str) -> str:
        """Saves a user preference or project fact into persistent memory."""
        if self.memory.save_memory_item(key, value):
            self.memory.log_audit("save_memory", 1, "VERIFIED", f"{key}={value}")
            return f"SUCCESS: Remembered '{key}': {value}"
        return "FAILED: Could not verify memory write."

    def recall_memories(self) -> str:
        """Retrieves all stored user preferences and memories."""
        memories = self.memory.load_memories()
        if not memories:
            return "No saved memories yet."
        return "\n".join([f"- {k}: {v['value']} (saved {v['updated_at']})" for k, v in memories.items()])

    def delete_memory(self, key: str) -> str:
        """Deletes a specific key from persistent memory."""
        if self.memory.delete_memory_item(key):
            self.memory.log_audit("delete_memory", 1, "VERIFIED", key)
            return f"SUCCESS: Deleted memory '{key}'."
        return f"FAILED: Memory key '{key}' not found."

    # --- Level 3: Destructive Actions (Requires Explicit UI Approval) ---
    def delete_file(self, filename: str) -> str:
        """Deletes a file inside ATLAS_Workspace after explicit user approval."""
        safe_name = os.path.basename(filename)
        filepath = os.path.join(WORKSPACE_DIR, safe_name)
        if not os.path.exists(filepath):
            return f"FAILED: File '{safe_name}' does not exist."

        approved = self.confirm.request_approval(
            "Permanently Delete File",
            f"File: {safe_name} (Cannot be undone)",
            risk_level=3
        )
        if not approved:
            self.memory.log_audit("delete_file", 3, "DENIED", safe_name)
            return f"CANCELLED: User denied deletion of '{safe_name}'."

        try:
            os.remove(filepath)
            if not os.path.exists(filepath):
                self.memory.log_audit("delete_file", 3, "VERIFIED", safe_name)
                return f"SUCCESS: Verified deletion of '{safe_name}'."
            return "FAILED: File still exists after removal attempt."
        except Exception as e:
            return f"FAILED: {e}"