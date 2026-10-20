import math
import struct
import collections
import threading
import pyaudio
import speech_recognition as sr
from typing import Callable, Optional, List


class STTEngine:
    SAMPLE_RATE = 16000
    CHUNK = 1024  # 64ms per frame at 16kHz

    def __init__(self, on_visualizer_level: Optional[Callable[[List[float]], None]] = None):
        self.recognizer = sr.Recognizer()
        # Hard limit network-backed speech recognition so a stalled request
        # cannot block the wake-word worker indefinitely.
        self.recognizer.operation_timeout = 7.0
        self.mic_lock = threading.Lock()
        self.on_visualizer_level = on_visualizer_level
        self.ambient_rms = 180.0
        self.last_language = "en"
        self._pa = pyaudio.PyAudio()
        # Move calibration to background thread so UI launches instantly
        threading.Thread(target=self.calibrate_ambient, daemon=True).start()

    def _compute_rms_and_Update_ui(self, pcm_bytes: bytes) -> float:
        count = len(pcm_bytes) // 2
        if count == 0:
            return 0.0
        shorts = struct.unpack(f"<{count}h", pcm_bytes)
        rms = math.sqrt(sum(s * s for s in shorts) / count)

        if self.on_visualizer_level:
            step = max(1, count // 5)
            bars = []
            for i in range(5):
                seg = shorts[i * step:(i + 1) * step]
                seg_rms = math.sqrt(sum(s * s for s in seg) / len(seg)) if seg else 0.0
                bars.append(min(1.0, seg_rms / 4200.0))
            self.on_visualizer_level(bars)
        return rms

    def calibrate_ambient(self, duration: float = 0.8):
        """Measures baseline room/fan RMS once on startup without crashing on busy devices."""
        with self.mic_lock:
            stream = None
            try:
                stream = self._pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.SAMPLE_RATE,
                    input=True,
                    frames_per_buffer=self.CHUNK,
                )
                num_frames = max(5, int((self.SAMPLE_RATE / self.CHUNK) * duration))
                vals = []
                for _ in range(num_frames):
                    data = stream.read(self.CHUNK, exception_on_overflow=False)
                    vals.append(self._compute_rms_and_Update_ui(data))
                if vals:
                    vals.sort()
                    median_rms = vals[len(vals) // 2]
                    self.ambient_rms = max(120.0, min(median_rms, 900.0))
            except Exception as e:
                print(f"[STT] Audio calibration safely skipped: {e}")
                self.ambient_rms = 180.0
            finally:
                if stream is not None:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except Exception:
                        pass

    def capture_utterance(
        self,
        wait_timeout: float = 5.0,
        silence_limit: float = 0.95,
        max_duration: float = 22.0,
        abort_check: Optional[Callable[[], bool]] = None,
    ) -> Optional[sr.AudioData]:
        """Captures an utterance and stops immediately once silence_limit is detected."""
        frame_duration = self.CHUNK / float(self.SAMPLE_RATE)
        pre_roll_frames = int(0.4 / frame_duration)
        max_Wait_frames = int(wait_timeout / frame_duration)
        max_Silence_frames = max(4, int(silence_limit / frame_duration))
        max_Total_frames = int(max_duration / frame_duration)

        with self.mic_lock:
            try:
                stream = self._pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.SAMPLE_RATE,
                    input=True,
                    frames_per_buffer=self.CHUNK,
                )
            except Exception:
                return None
            
            try:
                pre_roll = collections.deque(maxlen=pre_roll_frames)
                recorded_frames = []
                speech_started = False
                silent_frames = 0
                waited_frames = 0
                peak_rms = self.ambient_rms * 2.0

                start_trigger = max(self.ambient_rms * 2.1, self.ambient_rms + 130.0, 240.0)

                for _ in range(max_Total_frames):
                    if abort_check and abort_check():
                        return None

                    data = stream.read(self.CHUNK, exception_on_overflow=False)
                    rms = self._compute_rms_and_Update_ui(data)

                    if not speech_started:
                        pre_roll.append(data)
                        waited_frames += 1
                        if rms < start_trigger * 0.85:
                            self.ambient_rms = max(110.0, min(900.0, 0.96 * self.ambient_rms + 0.04 * rms))
                            start_trigger = max(self.ambient_rms * 2.1, self.ambient_rms + 130.0, 240.0)

                        if rms >= start_trigger:
                            speech_started = True
                            peak_rms = max(peak_rms, rms)
                            recorded_frames.extend(pre_roll)
                        elif waited_frames >= max_Wait_frames:
                            return None
                    else:
                        recorded_frames.append(data)
                        if rms > peak_rms:
                            peak_rms = rms

                        keep_threshold = max(
                            self.ambient_rms * 1.45,
                            self.ambient_rms + 75.0,
                            min(peak_rms * 0.20, 650.0),
                        )

                        if rms < keep_threshold:
                            silent_frames += 1
                            if silent_frames >= max_Silence_frames:
                                break
                        else:
                            silent_frames = 0

                if not speech_started or len(recorded_frames) < 4:
                    return None

                raw_bytes = b"".join(recorded_frames)
                return sr.AudioData(raw_bytes, self.SAMPLE_RATE, 2)
            finally:
                stream.stop_stream()
                stream.close()

    def transcribe(self, audio: sr.AudioData, language: Optional[str] = None) -> str:
        """Recognize speech with optional fixed language for wake-word verification."""
        if language:
            try:
                return self.recognizer.recognize_google(audio, language=language).strip()
            except sr.UnknownValueError:
                return ""

        last_unknown = None
        preferred = "hi-IN" if self.last_language == "hi" else "en-IN"
        alternatives = [preferred, "en-IN" if preferred == "hi-IN" else "hi-IN"]
        for lang in alternatives:
            try:
                text = self.recognizer.recognize_google(audio, language=lang)
                if text and text.strip():
                    self.last_language = "hi" if lang == "hi-IN" else "en"
                    return text.strip()
            except sr.UnknownValueError as exc:
                last_unknown = exc
                continue
            except sr.RequestError as exc:
                raise RuntimeError(f"Speech recognition network/service error: {exc}") from exc
        if last_unknown:
            raise last_unknown
        return ""
