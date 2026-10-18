from datetime import datetime, timedelta

from memory.config_manager import ConfigManager
from memory.memory_manager import MemoryManager
from actions.file_controller import FileController
from actions.reminder import parse_due_datetime


class ProactiveEngine:
    def __init__(self, config: ConfigManager, memory: MemoryManager, files: FileController):
        self.config = config
        self.memory = memory
        self.files = files

    def generate_daily_briefing(self) -> str:
        """Summarize today's tasks, overdue items, interrupted work, and maintenance."""
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        active = self.memory.get_active_tasks()

        today_tasks = [t for t in active if str(t.get("due_time", "")).startswith(today_str)]
        overdue_tasks = []
        for task in active:
            try:
                if parse_due_datetime(task.get("due_time", ""), now=now) < now:
                    overdue_tasks.append(task)
            except ValueError:
                continue

        memories = self.memory.load_all_memories()
        task_state = memories.get("task_state", {})
        resume_info = ""
        if task_state.get("objective") and task_state.get("resume_point"):
            resume_info = (
                f"\n- **Unfinished Task Checkpoint:** '{task_state['objective']}' "
                f"(Resume at: {task_state['resume_point']})"
            )

        maint_result = self.files.find_duplicates_or_large_files(large_threshold_kb=1024)
        maint = maint_result.splitlines()[0] if maint_result else "Workspace scan unavailable."
        return (
            f"☀️ **Daily Briefing ({now.strftime('%A, %b %d - %H:%M')})**\n"
            f"- **Tasks Due Today:** {len(today_tasks)}\n"
            f"- **Overdue Tasks:** {len(overdue_tasks)}"
            f"{resume_info}\n"
            f"- **Workspace Maintenance:** {maint}"
        )

    def check_due_and_nudges(self) -> list[tuple[str, str]]:
        """Return one notification per due reminder; preserve second-level timing."""
        if self.config.is_quiet_hours():
            return []

        now = datetime.now()
        try:
            lead_mins = max(0, int(self.config.get("deadline_nudge_minutes", 15)))
        except (ValueError, TypeError):
            lead_mins = 15
        notifications: list[tuple[str, str]] = []
        changed = False

        # Keep the read/check/write transaction atomic against reminder creation,
        # snooze, completion, and reschedule operations in other threads.
        with self.memory.tasks_lock:
            tasks = self.memory.load_tasks()
            for task in tasks:
                if task.get("status", "pending") != "pending" or task.get("notified"):
                    continue
                try:
                    due = parse_due_datetime(task.get("due_time", ""), now=now)
                except ValueError:
                    continue

                remaining = due - now
                title = task.get("title", "Reminder")
                due_label = due.strftime("%Y-%m-%d %H:%M:%S")
                if remaining.total_seconds() <= 0:
                    task["notified"] = True
                    task["status"] = "notified"
                    changed = True
                    notifications.append((
                        f"🔔 **Reminder Due:** {title} (Scheduled: {due_label})",
                        f"Reminder: {title}",
                    ))
                # Don't emit an almost-immediate heads-up for very short timers.
                elif (
                    not task.get("nudged")
                    and lead_mins > 0
                    and timedelta(minutes=1) < remaining <= timedelta(minutes=lead_mins)
                ):
                    task["nudged"] = True
                    changed = True
                    mins_left = max(1, int((remaining.total_seconds() + 59) // 60))
                    notifications.append((
                        f"⏳ **Upcoming Deadline ({mins_left} min):** {title}",
                        f"Heads up: {title} is due in {mins_left} minutes.",
                    ))

            if changed:
                self.memory.save_tasks(tasks)

        return notifications
