from datetime import datetime, timedelta
from memory.config_manager import ConfigManager
from memory.memory_manager import MemoryManager
from actions.file_controller import FileController


class ProactiveEngine:
    def __init__(self, config: ConfigManager, memory: MemoryManager, files: FileController):
        self.config = config
        self.memory = memory
        self.files = files

    def generate_daily_briefing(self) -> str:
        """Generates a daily briefing covering today's tasks, overdue items, interrupted work, and maintenance tips."""
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        active = self.memory.get_active_tasks()

        today_tasks = [t for t in active if t["due_time"].startswith(today_str)]
        overdue_tasks = [
            t for t in active
            if datetime.strptime(t["due_time"], "%Y-%m-%d %H:%M") < now
        ]

        memories = self.memory.load_all_memories()
        task_state = memories.get("task_state", {})
        resume_info = ""
        if task_state.get("objective") and task_state.get("resume_point"):
            resume_info = f"\n- **Unfinished Task Checkpoint:** '{task_state['objective']}' (Resume at: {task_state['resume_point']})"

        maint = self.files.find_duplicates_or_large_files(large_threshold_kb=1024).splitlines()[0]

        briefing = (
            f"☀️ **Daily Briefing ({now.strftime('%A, %b %d - %H:%M')})**\n"
            f"- **Tasks Due Today:** {len(today_tasks)}\n"
            f"- **Overdue Tasks:** {len(overdue_tasks)}"
            f"{resume_info}\n"
            f"- **Workspace Maintenance:** {maint}"
        )
        return briefing

    def check_due_and_nudges(self) -> list[tuple[str, str]]:
        """
        Returns a list of (display_message, speech_message) for due reminders
        and upcoming deadline nudges. Respects quiet hours.
        """
        if self.config.is_quiet_hours():
            return []

        tasks = self.memory.load_tasks()
        now = datetime.now()
        lead_mins = int(self.config.get("deadline_nudge_minutes", 15))
        notifications = []
        changed = False

        for t in tasks:
            if t.get("status", "pending") != "pending" or t.get("notified"):
                continue
            try:
                due = datetime.strptime(t["due_time"], "%Y-%m-%d %H:%M")
                if now >= due:
                    t["notified"] = True
                    t["status"] = "notified"
                    changed = True
                    notifications.append((
                        f"🔔 **Reminder Due:** {t['title']} (Scheduled: {t['due_time']})",
                        f"Reminder: {t['title']}"
                    ))
                elif not t.get("nudged") and (due - now) <= timedelta(minutes=lead_mins):
                    t["nudged"] = True
                    changed = True
                    mins_left = max(1, int((due - now).total_seconds() // 60))
                    notifications.append((
                        f"⏳ **Upcoming Deadline ({mins_left} min):** {t['title']}",
                        f"Heads up: {t['title']} is due in {mins_left} minutes."
                    ))
            except Exception:
                pass

        if changed:
            self.memory.save_tasks(tasks)
        return notifications