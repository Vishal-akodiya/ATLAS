import re
from datetime import datetime, timedelta
from typing import Optional

from memory.memory_manager import MemoryManager


_DURATION_RE = re.compile(
    r"^(?:(?:in|after|for)\s+)?(?P<amount>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d)"
    r"(?:\s+(?:from\s+now))?$",
    re.IGNORECASE,
)


def parse_due_datetime(value: str, now: Optional[datetime] = None) -> datetime:
    """Parse absolute timestamps or short natural durations such as 'in 8 seconds'."""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A due time is required.")

    now = now or datetime.now()
    text = value.strip()
    lowered = text.casefold().strip()

    if lowered in {"now", "right now", "immediately", "asap"}:
        return now

    duration_match = _DURATION_RE.fullmatch(lowered)
    if duration_match:
        amount = float(duration_match.group("amount"))
        unit = duration_match.group("unit").casefold()
        if unit.startswith("s"):
            delta = timedelta(seconds=amount)
        elif unit.startswith("m"):
            delta = timedelta(minutes=amount)
        elif unit.startswith("h"):
            delta = timedelta(hours=amount)
        else:
            delta = timedelta(days=amount)
        return now + delta

    # Accept common natural-language forms that a tool caller may provide.
    cleaned = re.sub(r"\s+at\s+", " ", text, flags=re.IGNORECASE)
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %I:%M:%S %p",
        "%Y-%m-%d %I:%M %p",
        "%B %d %Y %I:%M %p",
        "%b %d %Y %I:%M %p",
        "%I:%M:%S %p",
        "%I:%M %p",
        "%H:%M:%S",
        "%H:%M",
    )
    for fmt in formats:
        try:
            parsed = datetime.strptime(cleaned, fmt)
            if fmt in ("%I:%M:%S %p", "%I:%M %p", "%H:%M:%S", "%H:%M"):
                parsed = parsed.replace(year=now.year, month=now.month, day=now.day)
                if parsed <= now:
                    parsed += timedelta(days=1)
            return parsed
        except ValueError:
            continue

    # ISO variants with timezone-free local timestamps.
    try:
        parsed = datetime.fromisoformat(cleaned)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed
    except ValueError:
        pass

    raise ValueError(
        "Unsupported due time. Use a date/time like '2026-10-18 18:30' "
        "or a duration like 'in 10 seconds' / 'in 2 minutes'."
    )


def format_due_datetime(value: datetime) -> str:
    """Store seconds so sub-minute reminders remain accurate."""
    return value.strftime("%Y-%m-%d %H:%M:%S")


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
        """Create a persistent reminder. due_time_str may be an absolute time or a relative duration such as 'in 10 seconds', 'in 5 minutes', or '18:30'."""
        title = (title or "").strip()
        if not title:
            return "FAILED: Please provide a task title."
        try:
            due_dt = parse_due_datetime(due_time_str)
        except (ValueError, TypeError) as exc:
            return f"FAILED: Invalid reminder time. {exc}"

        due_formatted = format_due_datetime(due_dt)
        priority = (priority or "medium").strip().lower()
        if priority not in {"low", "medium", "high"}:
            priority = "medium"
        steps = [s.strip() for s in steps_csv.split(",") if s.strip()] if steps_csv else []

        # The lock makes ID allocation and read-modify-write atomic across UI,
        # voice-command, and reminder-scheduler threads.
        with self.memory.tasks_lock:
            tasks = self.memory.load_tasks()
            task_id = max([int(t.get("id", 0)) for t in tasks] + [0]) + 1
            new_task = {
                "id": task_id,
                "title": title,
                "due_time": due_formatted,
                "priority": priority,
                "steps": steps,
                "status": "pending",
                "notified": False,
                "nudged": False,
            }
            tasks.append(new_task)
            self.memory.save_tasks(tasks)
            self.memory.log_audit("create_task", 1, "VERIFIED", f"#{task_id} {title} @ {due_formatted}")

        return f"VERIFIED: Reminder #{task_id} '{title}' set for {due_formatted}."

    def list_tasks(self) -> str:
        """List active tasks grouped into Overdue, Due Today, and Upcoming."""
        tasks = self.memory.get_active_tasks()
        if not tasks:
            return "No active pending tasks."

        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        overdue, today, upcoming = [], [], []

        for task in tasks:
            due_raw = task.get("due_time", "")
            line = f"ID #{task.get('id', '?')} [{task.get('priority', 'medium').upper()}]: {task.get('title', 'Untitled')} (Due: {due_raw})"
            if task.get("steps"):
                line += f" | Steps: {' -> '.join(task['steps'])}"
            try:
                due_dt = parse_due_datetime(due_raw, now=now)
                if due_dt < now:
                    overdue.append(line)
                elif due_dt.strftime("%Y-%m-%d") == today_str:
                    today.append(line)
                else:
                    upcoming.append(line)
            except ValueError:
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
        """Snooze a task by the specified number of minutes."""
        try:
            minutes = max(1, int(minutes))
            task_id = int(task_id)
        except (ValueError, TypeError):
            return "FAILED: Task ID and snooze duration must be numbers."

        with self.memory.tasks_lock:
            tasks = self.memory.load_tasks()
            for task in tasks:
                if int(task.get("id", -1)) == task_id:
                    due_dt = datetime.now() + timedelta(minutes=minutes)
                    task["due_time"] = format_due_datetime(due_dt)
                    task["notified"] = False
                    task["nudged"] = False
                    task["status"] = "pending"
                    self.memory.save_tasks(tasks)
                    self.memory.log_audit("snooze_task", 1, "VERIFIED", f"#{task_id} +{minutes}m")
                    return f"VERIFIED: Snoozed reminder #{task_id} until {task['due_time']}."
        return f"FAILED: Task ID #{task_id} not found."

    def reschedule_task(self, task_id: int, new_due_time_str: str) -> str:
        """Reschedule a reminder; accepts absolute time or relative duration strings."""
        try:
            task_id = int(task_id)
            due_dt = parse_due_datetime(new_due_time_str)
        except (ValueError, TypeError) as exc:
            return f"FAILED: Invalid task ID or due time. {exc}"
        due_formatted = format_due_datetime(due_dt)

        with self.memory.tasks_lock:
            tasks = self.memory.load_tasks()
            for task in tasks:
                if int(task.get("id", -1)) == task_id:
                    task["due_time"] = due_formatted
                    task["notified"] = False
                    task["nudged"] = False
                    task["status"] = "pending"
                    self.memory.save_tasks(tasks)
                    self.memory.log_audit("reschedule_task", 1, "VERIFIED", f"#{task_id} -> {due_formatted}")
                    return f"VERIFIED: Reminder #{task_id} rescheduled to {due_formatted}."
        return f"FAILED: Task ID #{task_id} not found."

    def cancel_task(self, task_id: int) -> str:
        """Marks a reminder as completed/cancelled."""
        try:
            task_id = int(task_id)
        except (ValueError, TypeError):
            return "FAILED: Task ID must be a number."

        with self.memory.tasks_lock:
            tasks = self.memory.load_tasks()
            for task in tasks:
                if int(task.get("id", -1)) == task_id:
                    task["notified"] = True
                    task["status"] = "completed"
                    self.memory.save_tasks(tasks)
                    self.memory.log_audit("cancel_task", 1, "VERIFIED", f"#{task_id}")
                    return f"VERIFIED: Reminder #{task_id} marked completed."
        return f"FAILED: Task ID #{task_id} not found."
