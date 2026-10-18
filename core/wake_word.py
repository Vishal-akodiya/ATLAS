import time
import queue
import difflib
import threading
import speech_recognition as sr
from typing import Callable
from core.stt import STTEngine
from core.tts import TTSEngine

WAKE_ALIASES = (
    "atlas",
    "altas",
    "at last",
    "atless",
    "atalas",
    "at los",
    "outlast",
    "alice",
)

STOP_COMMANDS = ("stop", "atlas stop", "altas stop", "emergency stop", "cancel", "shut up")


class WakeWordListener:
    def __init__(
        self,
        stt: STTEngine,
        tts: TTSEngine,
        on_wake_detected: Callable[[], None],
        on_command_ready: Callable[[str], None],
        on_emergency_stop: Callable[[], None],
        on_status_change: Callable[[str, str, bool], None],
    ):
        self.stt = stt
        self.tts = tts
        self.on_wake_detected = on_wake_detected
        self.on_command_ready = on_command_ready
        self.on_emergency_stop = on_emergency_stop
        self.on_status_change = on_status_change

        self.muted = False
        self.wake_enabled = True
        self.is_busy = False
        self._audio_queue: queue.Queue[sr.AudioData] = queue.Queue(maxsize=6)
        self._followup_flag = threading.Event()

    @staticmethod
    def match_wake_word(transcript: str) -> tuple[bool, str]:
        text = transcript.lower().strip()
        for alias in WAKE_ALIASES:
            if alias in text:
                idx = text.find(alias)
                remainder = text[idx + len(alias):].strip(" ,.!?")
                return True, remainder

        words = text.split()
        for i, word in enumerate(words):
            clean_w = word.strip(".,!?")
            if difflib.SequenceMatcher(None, clean_w, "atlas").ratio() >= 0.72:
                remainder = " ".join(words[i + 1:]).strip(" ,.!?")
                return True, remainder
        return False, ""

    def start(self):
        threading.Thread(target=self._capture_loop, daemon=True).start()
        threading.Thread(target=self._recognize_worker, daemon=True).start()

    def _capture_loop(self):
        while True:
            if self.muted or not self.wake_enabled or self.is_busy or self.tts.is_speaking.is_set():
                time.sleep(0.08)
                continue

            # If "Atlas" was just spoken by itself, listen for the follow-up question with a 1.0s silence cutoff
            if self._followup_flag.is_set():
                self._followup_flag.clear()
                self.is_busy = True
                try:
                    self.on_status_change("Wake word detected · listening for command…", "#f59e0b", True)
                    audio = self.stt.capture_utterance(
                        wait_timeout=6.0,
                        silence_limit=1.0,
                        max_duration=25.0,
                        abort_check=lambda: self.muted,
                    )
                    if audio:
                        self.on_status_change("Transcribing...", "#f59e0b", True)
                        full_q = self.stt.transcribe(audio)
                        if full_q:
                            self.on_command_ready(full_q)
                        else:
                            self.on_status_change("Didn't catch that · listening for 'Atlas'…", "#f59e0b", False)
                    else:
                        self.on_status_change("Listening for 'Atlas'…", "#10b981", False)
                except sr.UnknownValueError:
                    self.on_status_change("Didn't catch that · listening for 'Atlas'…", "#f59e0b", False)
                except Exception as exc:
                    print(f"[Wake Word] Follow-up capture failed: {exc}")
                    self.on_status_change("Listening for 'Atlas'…", "#10b981", False)
                finally:
                    self.is_busy = False
                continue

            # Passive wake-word capture: snaps shut 0.8s after speech ends.
            # A transient microphone/driver error must not permanently kill this thread.
            try:
                audio = self.stt.capture_utterance(
                    wait_timeout=1.5,
                    silence_limit=0.80,
                    max_duration=14.0,
                    abort_check=lambda: self.muted or self.is_busy or self.tts.is_speaking.is_set() or self._followup_flag.is_set(),
                )
                if audio and not self.tts.is_speaking.is_set() and not self.is_busy:
                    try:
                        self._audio_queue.put_nowait(audio)
                    except queue.Full:
                        # Drop the oldest buffered recording to keep wake detection responsive.
                        try:
                            self._audio_queue.get_nowait()
                            self._audio_queue.task_done()
                        except queue.Empty:
                            pass
                        try:
                            self._audio_queue.put_nowait(audio)
                        except queue.Full:
                            pass
            except Exception as exc:
                print(f"[Wake Word] Passive capture failed: {exc}")
                time.sleep(0.25)

    def _recognize_worker(self):
        while True:
            audio = self._audio_queue.get()
            if self.muted:
                self._audio_queue.task_done()
                continue
            try:
                transcript = self.stt.transcribe(audio).strip()
                low = transcript.lower()

                # Immediate emergency stop detection
                if low in STOP_COMMANDS:
                    self.on_emergency_stop()
                    continue

                matched, command = self.match_wake_word(transcript)
                if matched:
                    if command.lower() in ("stop", "cancel"):
                        self.on_emergency_stop()
                        continue

                    # Mark the listener busy before stopping TTS so the TTS-idle
                    # callback cannot overwrite the wake-word status in the UI.
                    self.is_busy = True
                    if not command.strip():
                        self._followup_flag.set()
                    try:
                        self.tts.stop()
                        self.on_wake_detected()
                        if command.strip():
                            self.on_status_change("Command captured · processing…", "#f59e0b", True)
                            self.on_command_ready(command)
                    finally:
                        self.is_busy = False
            except (sr.UnknownValueError, sr.RequestError):
                pass
            finally:
                self._audio_queue.task_done()