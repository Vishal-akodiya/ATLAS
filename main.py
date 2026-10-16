import re
import time
import threading
from datetime import datetime
import speech_recognition as sr

from memory.config_manager import ConfigManager
from memory.memory_manager import MemoryManager
from core.confirm import ConfirmationGate
from core.undo import UndoManager
from core.tts import TTSEngine
from core.stt import STTEngine
from core.wake_word import WakeWordListener
from core.gemini import GeminiEngine

from actions.desktop import DesktopActions
from actions.screen_processor import ScreenProcessor
from actions.file_controller import FileController
from actions.web_search import WebResearchActions
from actions.reminder import ReminderActions
from actions.send_message import CommunicationActions
from actions.system_monitor import SystemMonitorActions
from actions.proactive import ProactiveEngine
from ui import AtlasUI


class AtlasOperator:
    def __deepcopy__(self, memo):
        return self

    def __init__(self):
        self.ui: AtlasUI = None
        self.is_processing = False

        self.config = ConfigManager()
        self.memory = MemoryManager(
            on_tasks_updated=lambda tasks: self.ui.render_tasks(tasks) if self.ui else None,
            on_memories_updated=lambda mems: self.ui.render_memories(mems) if self.ui else None,
        )
        self.confirm = ConfirmationGate()
        self.undo = UndoManager()

        self.desktop_actions = DesktopActions(
            self.config,
            self.memory,
            self.confirm,
            on_action_status=lambda msg: self.ui.set_action_banner(msg) if self.ui else None,
        )
        self.screen_processor = ScreenProcessor(
            self.memory,
            self.desktop_actions,
            on_preview_Callback=lambda path: self.ui.show_screen_preview(path) if self.ui else None,
            on_action_status=lambda msg: self.ui.set_action_banner(msg) if self.ui else None,
        )
        # Bind ScreenProcessor to DesktopActions for visual WhatsApp execution
        self.desktop_actions.bind_screen_processor(self.screen_processor)

        self.file_actions = FileController(self.memory, self.confirm, self.undo)
        self.web_actions = WebResearchActions(self.memory)
        self.reminder_actions = ReminderActions(self.memory)
        self.comm_actions = CommunicationActions(self.memory, self.confirm)
        self.sys_actions = SystemMonitorActions(self.config, self.memory, self.confirm)
        self.proactive = ProactiveEngine(self.config, self.memory, self.file_actions)

        self.tts = TTSEngine(self.config)
        self.stt = STTEngine(on_visualizer_level=lambda bars: self.ui.update_visualizer(bars) if self.ui else None)
        self.gemini = GeminiEngine(self._build_tool_list())
        self.screen_processor.bind_gemini(self.gemini)

        self.ui = AtlasUI(
            on_ask_text=self.handle_text_query,
            on_ask_screen=self.handle_screen_query,
            on_manual_voice=self.handle_manual_voice,
            on_stop_all=self.handle_emergency_stop,
            on_clear_chat=self.gemini.reset_chat,
            on_complete_task=self.reminder_actions.cancel_task,
            on_snooze_task=lambda tid: self.reminder_actions.snooze_task(tid, 15),
            on_delete_memory=self._ui_delete_memory,
            on_undo=self.handle_undo,
            on_briefing=self.handle_daily_briefing,
            on_toggle_mute=self.handle_mute_toggle,
            on_toggle_quiet=self.handle_quiet_toggle,
            on_approval_decision=self.confirm.resolve,
        )
        self.confirm.bind_ui(self.ui.show_approval_prompt)
        self.screen_processor.bind_window_controls(
            hide_cb=lambda: self.ui.safe_call(self.ui.withdraw),
            show_cb=lambda: self.ui.safe_call(self.ui.deiconify),
        )

        self.wake_listener = WakeWordListener(
            stt=self.stt,
            tts=self.tts,
            on_wake_detected=lambda: self.ui.set_status("Atlas Awake!", "#ef4444", True),
            on_command_ready=self.handle_voice_command,
            on_emergency_stop=self.handle_emergency_stop,
            on_status_change=self.ui.set_status,
        )

    # ==========================================
    # INSTANT LOCAL REFLEX ROUTER (< 0.05s)
    # ==========================================
    def _try_instant_reflex(self, prompt: str) -> str | None:
        clean = prompt.strip()
        low = clean.lower()

        # WhatsApp Visual Flow Reflex:
        # e.g., "send a whatsapp message to Rahul saying I am on my way"
        wa_match = re.search(
            r"(?:send\s+(?:a\s+)?(?:whatsapp\s+)?(?:message\s+)?to|whatsapp)\s+([a-zA-Z0-9_ \-]+?)\s+(?:saying|that|message|:)\s+(.+)$",
            clean,
            flags=re.IGNORECASE,
        )
        if wa_match and "whatsapp" in low:
            contact = wa_match.group(1).strip()
            msg_body = wa_match.group(2).strip().strip("\"'")
            res = self.screen_processor.visual_send_whatsapp(contact, msg_body)
            return f"**{res}**"

        # Direct Open App Reflex
        if " and " not in low:
            open_match = re.match(r"^(?:please\s+)?(?:open|launch|start)\s+([a-zA-Z0-9_ \-\.]+)$", clean, flags=re.IGNORECASE)
            if open_match:
                app_target = open_match.group(1).strip()
                if not any(w in app_target.lower() for w in ("http", "www.", ".com", "file", "document")):
                    res = self.desktop_actions.open_app(app_target)
                    return f"**{res}**"

        # Time Reflex
        if low in ("what time is it", "what time is it?", "current time", "tell me the time", "what is the time"):
            return f"It is currently **{self.get_current_time()}**."

        # System Status Reflex
        if low in ("check my cpu, ram, and disk space status.", "system status", "check system status", "system health"):
            return self.sys_actions.check_system_status()

        # Installed Apps Reflex
        if low in ("list the applications installed on my computer.", "list installed apps", "show installed apps"):
            return self.desktop_actions.list_installed_apps()

        # Tasks Reflex
        if low in ("list tasks", "show my tasks", "what are my tasks", "show reminders"):
            return self.reminder_actions.list_tasks()

        # Undo Reflex
        if low in ("undo", "undo last action", "undo that"):
            return f"↩️ **{self.undo.undo_last()}**"

        return None

    def get_current_time(self) -> str:
        return datetime.now().strftime("%A, %B %d, %Y - %H:%M")

    def save_user_memory(self, category: str, key: str, value: str) -> str:
        ok, msg = self.memory.save_memory(category, key, value)
        self.memory.log_audit("save_user_memory", 1, "VERIFIED" if ok else "BLOCKED", msg)
        return msg

    def search_user_memory(self, query: str = "") -> str:
        data = self.memory.load_all_memories()
        lines = []
        for cat in ("profile", "workspace"):
            for k, v in data.get(cat, {}).items():
                if not query or query.lower() in k.lower() or query.lower() in str(v.get("value", "")).lower():
                    lines.append(f"[{cat.upper()}] {k}: {v['value']} (Updated: {v['updated_at']})")
        ts = data.get("task_state", {})
        if ts.get("objective"):
            lines.append(f"[ACTIVE_TASK_STATE] Objective: {ts['objective']} | Resume: {ts.get('resume_point', '')}")
        return "\n".join(lines) if lines else "No matching memories found."

    def delete_user_memory(self, category: str, key: str) -> str:
        if self.memory.delete_memory(category, key):
            return f"VERIFIED: Deleted memory '{key}'."
        return f"FAILED: Memory key '{key}' not found."

    def save_task_checkpoint(self, objective: str, completed_step: str, resume_point: str) -> str:
        self.memory.update_task_checkpoint(objective, completed_step, resume_point)
        return f"VERIFIED: Task checkpoint saved for '{objective}'."

    def undo_last_action(self) -> str:
        return self.undo.undo_last()

    def _build_tool_list(self) -> list:
        return [
            self.get_current_time,
            self.screen_processor.inspect_screen_state,
            self.screen_processor.locate_and_interact_on_screen,
            self.desktop_actions.open_app,
            self.desktop_actions.list_installed_apps,
            self.desktop_actions.send_whatsapp_message,
            self.desktop_actions.focus_window,
            self.desktop_actions.minimize_window,
            self.desktop_actions.type_text,
            self.desktop_actions.press_hotkey,
            self.desktop_actions.click_control,
            self.desktop_actions.scroll_screen,
            self.desktop_actions.close_app,
            self.file_actions.search_files,
            self.file_actions.read_document,
            self.file_actions.create_file,
            self.file_actions.move_file,
            self.file_actions.compare_documents,
            self.file_actions.find_duplicates_or_large_files,
            self.file_actions.delete_file,
            self.undo_last_action,
            self.web_actions.web_search,
            self.web_actions.extract_webpage_text,
            self.web_actions.open_page,
            self.save_user_memory,
            self.search_user_memory,
            self.delete_user_memory,
            self.save_task_checkpoint,
            self.reminder_actions.create_task,
            self.reminder_actions.list_tasks,
            self.reminder_actions.snooze_task,
            self.reminder_actions.reschedule_task,
            self.reminder_actions.cancel_task,
            self.comm_actions.draft_email,
            self.comm_actions.prepare_calendar_event,
            self.comm_actions.send_message,
            self.sys_actions.check_system_status,
            self.sys_actions.check_app_running,
            self.sys_actions.read_logs,
            self.sys_actions.run_approved_command,
            self.proactive.generate_daily_briefing,
        ]

    def _ui_delete_memory(self, category: str, key: str):
        self.memory.delete_memory(category, key)

    def handle_undo(self):
        msg = self.undo.undo_last()
        self.ui.add_assistant_bubble(f"↩️ **{msg}**")
        self.tts.speak(msg)

    def handle_daily_briefing(self):
        brief = self.proactive.generate_daily_briefing()
        self.ui.add_assistant_bubble(brief)
        self.tts.speak(brief)

    def handle_mute_toggle(self, is_muted: bool):
        self.wake_listener.muted = is_muted
        self.ui.set_status("Mic Muted" if is_muted else "Ready", "#94a3b8" if is_muted else "#10b981", False)

    def handle_quiet_toggle(self, is_quiet: bool):
        self.config.set("quiet_mode", is_quiet)
        if is_quiet:
            self.tts.stop()

    def handle_emergency_stop(self):
        self.desktop_actions.trigger_emergency_stop()
        self.tts.stop()
        self.confirm.resolve("cancel_task")
        self.ui.set_status("Emergency Stop Active", "#ef4444", False)

    def handle_text_query(self, question: str):
        if self.is_processing:
            return
        threading.Thread(target=self._run_gemini, args=(question, False), daemon=True).start()

    def handle_screen_query(self, question: str):
        if self.is_processing:
            return
        threading.Thread(target=self._run_gemini, args=(question, True), daemon=True).start()

    def handle_manual_voice(self):
        if self.is_processing:
            return
        threading.Thread(target=self._manual_voice_worker, daemon=True).start()

    def _manual_voice_worker(self):
        self.is_processing = True
        self.wake_listener.is_busy = True
        self.tts.stop()
        self.ui.set_status("Listening...", "#ef4444", True)
        try:
            audio = self.stt.capture_utterance(wait_timeout=6.0, silence_limit=0.90, max_duration=25.0)
            if audio:
                self.ui.set_status("Transcribing...", "#f59e0b", True)
                transcript = self.stt.transcribe(audio)
                if transcript:
                    self.handle_voice_command(transcript)
            else:
                self.ui.set_status("Listening timed out.", "#f59e0b", False)
        except sr.UnknownValueError:
            self.ui.set_status("Could not catch voice.", "#ef4444", False)
        except Exception as e:
            self.ui.add_assistant_bubble(f"**Voice Error:** {e}")
            self.ui.set_status("Ready", "#10b981", False)
        finally:
            self.is_processing = False
            self.wake_listener.is_busy = False

    def handle_voice_command(self, transcript: str):
        self.ui.update_input_box(transcript)
        screen_keywords = ("screen", "click", "button", "window", "type here", "look at", "whatsapp")
        needs_screen = any(kw in transcript.lower() for kw in screen_keywords)
        prefix = "🎙️ 🖥️ [Vision]: " if needs_screen else "🎙️ "
        self.ui.add_user_bubble(f"{prefix}{transcript}")
        self._run_gemini(transcript, with_screen=needs_screen)

    def _run_gemini(self, prompt: str, with_screen: bool = False):
        self.is_processing = True
        self.wake_listener.is_busy = True
        self.desktop_actions.clear_emergency_stop()
        try:
            # 1. Instant Reflex Router Check
            if not with_screen:
                instant_reply = self._try_instant_reflex(prompt)
                if instant_reply:
                    self.ui.add_assistant_bubble(instant_reply)
                    self.tts.speak(instant_reply)
                    return

            # 2. Vision and Tool Execution
            img_path = None
            if with_screen:
                self.ui.set_status("Capturing Screen...", "#06b6d4", True)
                img_path, _, _ = self.screen_processor.capture_raw_screen(hide_atlas=True)

            self.ui.set_status(f"Operating ({self.gemini.active_model})...", "#f59e0b", True)
            reply = self.gemini.send(prompt, image_path=img_path)
            self.ui.add_assistant_bubble(reply)
            self.tts.speak(reply)
        except Exception as e:
            self.ui.add_assistant_bubble(f"**Execution Error:** {e}")
        finally:
            self.is_processing = False
            self.wake_listener.is_busy = False
            self.ui.set_status("Ready", "#10b981", False)

    def _proactive_loop(self):
        while True:
            time.sleep(12)
            alerts = self.proactive.check_due_and_nudges()
            for ui_msg, tts_msg in alerts:
                self.ui.add_assistant_bubble(ui_msg)
                self.tts.speak(tts_msg)

    def run(self):
        self.ui.render_tasks(self.memory.get_active_tasks())
        self.ui.render_memories(self.memory.load_all_memories())
        self.wake_listener.start()
        threading.Thread(target=self._proactive_loop, daemon=True).start()
        self.ui.mainloop()


if __name__ == "__main__":
    app = AtlasOperator()
    app.run()