from datetime import datetime, timedelta
from memory.memory_manager import MemoryManager


class ReminderActions:
    def __init__(self, memory: MemoryManager):
        self.memory = memory

    def create_task(
        self,
        title: str,
        due_time_str: str,
        priority: str = "medium",
        steps_csv: str = "",
    ) -> str:
        """
        Creates a durable task/reminder.
        due_time_str MUST be 'YYYY-MM-DD HH:MM'.
        priority can be 'low', 'medium', or 'high'.
        """
        try:
            datetime.strptime(due_time_str, "%Y-%m-%d %H:%M")
        except ValueError:
            return "FAILED: Invalid due_time_str format. Use 'YYYY-MM-DD HH:MM' (call get_current_time first)."

        tasks = self.memory.load_tasks()
        task_id = max([t["id"] for t in tasks] + [0]) + 1
        steps = [s.strip() for s in steps_csv.split(",") if s.strip()] if steps_csv else []

        new_task = {
            "id": task_id,
            "title": title.strip(),
            "due_time": due_time_str,
            "priority": priority.strip().lower(),
            "steps": steps,
            "status": "pending",
            "notified": False,
            "nudged": False,
        }
        tasks.append(new_task)
        self.memory.save_tasks(tasks)
        self.memory.log_audit("create_task", 1, "VERIFIED", f"#{task_id} {title} @ {due_time_str}")
        return f"VERIFIED: Task #{task_id} ('{title}', priority={priority}) scheduled for {due_time_str}."

    def list_tasks(self) -> str:
        """Lists active tasks grouped into Overdue, Due Today, and Upcoming."""
        tasks = self.memory.get_active_tasks()
        if not tasks:
            return "No active pending tasks."

        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        overdue, today, upcoming = [], [], []

        for t in tasks:
            line = f"ID #{t['id']} [{t.get('priority', 'medium').upper()}]: {t['title']} (Due: {t['due_time']})"
            if t.get("steps"):
                line += f" | Steps: {' -> '.join(t['steps'])}"
            try:
                due_dt = datetime.strptime(t["due_time"], "%Y-%m-%d %H:%M")
                if due_dt < now:
                    overdue.append(line)
                elif t["due_time"].startswith(today_str):
                    today.append(line)
                else:
                    upcoming.append(line)
            except Exception:
                upcoming.append(line)

        out = []
        if overdue:
            out.append("⚠️ OVERDUE:\n" + "\n".join(overdue))
        if today:
            out.append("📅 TODAY:\n" + "\n".join(today))
        if upcoming:
            out.append("🔜 UPCOMING:\n" + "\n".join(upcoming))
        return "\n\n".join(out)

    def snooze_task(self, task_id: int, minutes: int = 15) -> str:
        """Snoozes a task by adding minutes to its due time."""
        tasks = self.memory.load_tasks()
        for t in tasks:
            if t["id"] == int(task_id):
                new_due = datetime.now() + timedelta(minutes=int(minutes))
                t["due_time"] = new_due.strftime("%Y-%m-%d %H:%M")
                t["notified"] = False
                t["nudged"] = False
                t["status"] = "pending"
                self.memory.save_tasks(tasks)
                self.memory.log_audit("snooze_task", 1, "VERIFIED", f"#{task_id} +{minutes}m")
                return f"VERIFIED: Snoozed Task #{task_id} until {t['due_time']}."
        return f"FAILED: Task ID #{task_id} not found."

    def reschedule_task(self, task_id: int, new_due_time_str: str) -> str:
        """Reschedules an existing task to a new 'YYYY-MM-DD HH:MM' timestamp."""
        try:
            datetime.strptime(new_due_time_str, "%Y-%m-%d %H:%M")
        except ValueError:
            return "FAILED: Invalid time format. Must be 'YYYY-MM-DD HH:MM'."

        tasks = self.memory.load_tasks()
        for t in tasks:
            if t["id"] == int(task_id):
                t["due_time"] = new_due_time_str
                t["notified"] = False
                t["nudged"] = False
                t["status"] = "pending"
                self.memory.save_tasks(tasks)
                self.memory.log_audit("reschedule_task", 1, "VERIFIED", f"#{task_id} -> {new_due_time_str}")
                return f"VERIFIED: Task #{task_id} rescheduled to {new_due_time_str}."
        return f"FAILED: Task ID #{task_id} not found."

    def cancel_task(self, task_id: int) -> str:
        """Marks a task as completed/cancelled."""
        tasks = self.memory.load_tasks()
        for t in tasks:
            if t["id"] == int(task_id):
                t["notified"] = True
                t["status"] = "completed"
                self.memory.save_tasks(tasks)
                self.memory.log_audit("cancel_task", 1, "VERIFIED", f"#{task_id}")
                return f"VERIFIED: Task #{task_id} marked completed/cancelled."
        return f"FAILED: Task ID #{task_id} not found."