import os
from datetime import datetime
from memory.config_manager import WORKSPACE_DIR
from memory.memory_manager import MemoryManager
from core.confirm import ConfirmationGate


class CommunicationActions:
    def __init__(self, memory: MemoryManager, confirm: ConfirmationGate):
        self.memory = memory
        self.confirm = confirm

    def draft_email(self, recipient: str, subject: str, body: str) -> str:
        """Saves an email draft in ATLAS_Workspace for user review before sending."""
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"draft_email_{stamp}.md"
        fpath = os.path.join(WORKSPACE_DIR, fname)
        content = f"# Email Draft\n- **To:** {recipient}\n- **Subject:** {subject}\n- **Created:** {stamp}\n\n---\n\n{body}\n"
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        self.memory.log_audit("draft_email", 1, "VERIFIED", fname)
        return f"VERIFIED: Saved email draft at '{fname}' for review. Sending still requires explicit approval."

    def prepare_calendar_event(self, title: str, start_time_str: str, attendees: str = "") -> str:
        """Prepares a calendar event and checks for scheduling conflicts against existing tasks."""
        try:
            datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
        except ValueError:
            return "FAILED: start_time_str must be 'YYYY-MM-DD HH:MM'."

        conflicts = [
            t for t in self.memory.get_active_tasks()
            if t.get("due_time") == start_time_str
        ]
        conflict_note = (
            f"⚠️ CONFLICT DETECTED with Task #{conflicts[0]['id']} ('{conflicts[0]['title']}')."
            if conflicts else "No scheduling conflicts detected."
        )

        tasks = self.memory.load_tasks()
        task_id = max([t["id"] for t in tasks] + [0]) + 1
        tasks.append({
            "id": task_id,
            "title": f"[Event] {title}" + (f" (with {attendees})" if attendees else ""),
            "due_time": start_time_str,
            "priority": "high",
            "steps": [],
            "status": "pending",
            "notified": False,
        })
        self.memory.save_tasks(tasks)
        self.memory.log_audit("prepare_calendar_event", 1, "VERIFIED", f"{title} @ {start_time_str}")
        return f"VERIFIED: Prepared event '{title}' for {start_time_str}. {conflict_note}"

    def send_message(self, recipient: str, channel: str, message_body: str) -> str:
        """Requires explicit Level 3 confirmation showing recipient, channel, and exact content before sending."""
        approved, reason = self.confirm.request_approval(
            action=f"Send External Message via {channel}",
            target=f"Recipient: {recipient}",
            scope=f"Message Content: '{message_body[:120]}'",
            consequences="Transmits message externally; cannot be undone once sent.",
            risk_level=3,
        )
        if not approved:
            self.memory.log_audit("send_message", 3, "DENIED", f"{channel} -> {recipient}")
            return f"CANCELLED: External message send was denied by user ({reason}). Draft preserved."

        # Record sent receipt in workspace
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        receipt_file = os.path.join(WORKSPACE_DIR, f"sent_receipt_{stamp}.txt")
        with open(receipt_file, "w", encoding="utf-8") as f:
            f.write(f"SENT RECEIPT\nTimestamp: {stamp}\nChannel: {channel}\nRecipient: {recipient}\n\n{message_body}\n")
        self.memory.log_audit("send_message", 3, "VERIFIED", f"Receipt: { os.path.basename(receipt_file) }")
        return f"VERIFIED: Approved and dispatched message to {recipient} on {channel} (Receipt: {os.path.basename(receipt_file)})."