import os
import subprocess
import psutil
from memory.config_manager import ConfigManager
from memory.memory_manager import MemoryManager
from core.confirm import ConfirmationGate


class SystemMonitorActions:
    def __init__(self, config: ConfigManager, memory: MemoryManager, confirm: ConfirmationGate):
        self.config = config
        self.memory = memory
        self.confirm = confirm

    def check_system_status(self) -> str:
        """Checks CPU usage, RAM usage, and available disk space."""
        cpu = psutil.cpu_percent(interval=0.2)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage(os.getcwd())
        free_gb = round(disk.free / (1024 ** 3), 2)
        total_gb = round(disk.total / (1024 ** 3), 2)
        report = (
            f"VERIFIED System Status:\n"
            f"- CPU Load: {cpu}%\n"
            f"- RAM Usage: {ram.percent}% ({round(ram.available / (1024**3), 2)} GB available)\n"
            f"- Disk Space: {free_gb} GB free of {total_gb} GB"
        )
        self.memory.log_audit("check_system_status", 0, "VERIFIED", f"CPU={cpu}%, FreeDisk={free_gb}GB")
        return report

    def check_app_running(self, app_name: str) -> str:
        """Checks whether a specific application or process is currently running."""
        matches = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if app_name.lower() in (proc.info["name"] or "").lower():
                    matches.append(f"{proc.info['name']} (PID {proc.info['pid']})")
            except Exception:
                pass
        self.memory.log_audit("check_app_running", 0, "VERIFIED", f"{app_name}: {len(matches)}")
        if not matches:
            return f"VERIFIED: '{app_name}' is NOT currently running."
        return f"VERIFIED: '{app_name}' is running ({len(matches)} processes): {', '.join(matches[:5])}"

    def read_logs(self, line_count: int = 20) -> str:
        """Reads recent entries from the ATLAS audit and troubleshooting log."""
        return self.memory.read_recent_logs(lines=int(line_count))

    def run_approved_command(self, command: str) -> str:
        """Runs a diagnostic command if it matches the command allowlist and receives Level 2 approval."""
        base_cmd = command.strip().split()[0].lower() if command.strip() else ""
        allowed = [c.lower() for c in self.config.get("allowed_commands", [])]
        if base_cmd not in allowed:
            self.memory.log_audit("run_approved_command", 4, "DENIED", command)
            return f"BLOCKED (Level 4 Restricted): Command '{base_cmd}' is not in the diagnostic allowlist ({', '.join(allowed)})."

        approved, reason = self.confirm.request_approval(
            action="Execute System Diagnostic Command",
            target=command,
            scope="Local non-admin shell (10s timeout)",
            consequences="Runs read-only diagnostic command and captures stdout.",
            risk_level=2,
        )
        if not approved:
            return f"CANCELLED: Command execution denied ({reason})."

        try:
            res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
            output = (res.stdout or res.stderr or "Command completed with no output.").strip()[:1500]
            self.memory.log_audit("run_approved_command", 2, "VERIFIED", command)
            return f"VERIFIED Command Output ({command}):\n{output}"
        except Exception as e:
            return f"FAILED: Command error or timeout - {e}"