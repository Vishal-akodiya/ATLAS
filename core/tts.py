import re
import time
import queue
import threading
import pythoncom
import win32com.client
from memory.config_manager import ConfigManager


class TTSEngine:
    def __init__(self, config: ConfigManager):
        self.config = config
        self.speech_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.is_speaking = threading.Event()
        threading.Thread(target=self._worker, daemon=True).start()

    @staticmethod
    def clean_for_speech(text: str) -> str:
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        text = re.sub(r"[*_#`]", "", text)
        text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
        return text.strip()

    def speak(self, text: str):
        if self.config.get("quiet_mode", False):
            return
        cleaned = self.clean_for_speech(text)
        if cleaned:
            self.stop_event.clear()
            self.speech_queue.put(cleaned)

    def stop(self):
        self.stop_event.set()
        with self.speech_queue.mutex:
            self.speech_queue.queue.clear()
        self.speech_queue.put("__STOP__")

    def _worker(self):
        pythoncom.CoInitialize()
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        speaker.Rate = 0
        speaker.Volume = 100

        george_voice = None
        hemant_voice = None
        default_voice = None

        voices = speaker.GetVoices()
        for i in range(voices.Count):
            desc = voices.Item(i).GetDescription().lower()
            if "george" in desc:
                george_voice = voices.Item(i)
            elif "hemant" in desc:
                hemant_voice = voices.Item(i)
            elif "david" in desc:
                default_voice = voices.Item(i)

        if voices.Count > 0:
            speaker.Voice = george_voice or default_voice or voices.Item(0)

        while True:
            text = self.speech_queue.get()
            if text == "__STOP__":
                speaker.Speak("", 2)
                self.is_speaking.clear()
                self.speech_queue.task_done()
                continue

            if text and not self.stop_event.is_set() and not self.config.get("quiet_mode", False):
                self.is_speaking.set()
                try:
                    is_hindi = bool(re.search(r"[\u0900-\u097F]", text))
                    if is_hindi and hemant_voice:
                        speaker.Voice = hemant_voice
                    elif not is_hindi and (george_voice or default_voice):
                        speaker.Voice = george_voice or default_voice

                    sentences = re.split(r"(?<=[.!?]) +", text)
                    for sentence in sentences:
                        if self.stop_event.is_set():
                            speaker.Speak("", 2)
                            break
                        if sentence.strip():
                            speaker.Speak(sentence.strip(), 1)
                            while speaker.Status.RunningState == 2:
                                if self.stop_event.is_set():
                                    speaker.Speak("", 2)
                                    break
                                time.sleep(0.04)
                finally:
                    time.sleep(0.15)
                    self.is_speaking.clear()

            self.speech_queue.task_done()