import threading
from typing import Callable, Optional, Dict


class ConfirmationGate:
    """Enforces Risk Levels 0-4 with structured user-visible approval prompts."""

    def __init__(self):
        self._ui_callback: Optional[Callable[[Dict[str, str]], None]] = None
        self._event = threading.Event()
        self._decision = "deny"

    def bind_ui(self, callback: Callable[[Dict[str, str]], None]):
        self._ui_callback = callback

    def request_approval(
        self,
        action: str,
        target: str,
        scope: str,
        consequences: str,
        risk_level: int = 2,
        timeout: float = 45.0,
    ) -> tuple[bool, str]:
        """
        Risk Levels:
        0 - Read-only (Auto-allowed)
        1 - Reversible (Auto-allowed within allowlist)
        2 - Material change (Requires approval)
        3 - External or destructive (Requires explicit confirmation)
        4 - Restricted (Always denied)
        """
        if risk_level <= 1:
            return True, "auto_approved"
        if risk_level >= 4:
            return False, "restricted_level_4_denied"
        if not self._ui_callback:
            return False, "no_ui_bound"

        self._event.clear()
        self._decision = "deny"

        payload = {
            "level": f"Level {risk_level} ({'Material Change' if risk_level == 2 else 'External / Destructive'})",
            "action": action,
            "target": target,
            "scope": scope,
            "consequences": consequences,
        }
        self._ui_callback(payload)

        responded = self._event.wait(timeout=timeout)
        if not responded:
            return False, "timeout"
        return (self._decision == "approve_once"), self._decision

    def resolve(self, choice: str):
        """choice is 'approve_once', 'deny', or 'cancel_task'."""
        self._decision = choice
        self._event.set()