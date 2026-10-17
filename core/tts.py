import re
import math
import time
import random
import queue
import threading
import asyncio
import os
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

from memory.config_manager import ConfigManager

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

def _to_numpy(samples) -> np.ndarray:
    if hasattr(samples, "detach"):
        t = samples.detach().cpu().float()
        try:
            return t.numpy()
        except RuntimeError:
            return np.asarray(t.tolist(), dtype=np.float32)
    return np.asarray(samples, dtype=np.float32)

def _compress_silence(
    arr: np.ndarray, sample_rate: int = 24_000, max_silence_ms: int = 250, threshold: float = 0.01
) -> np.ndarray:
    """Aggressively trims unnatural punctuation pauses (1.5s+) left by neural TTS."""
    max_samp = int(max_silence_ms * sample_rate / 1000)
    frame_len = 240
    out: list[np.ndarray] = []
    silent_acc = 0
    for i in range(0, len(arr), frame_len):
        chunk = arr[i : i + frame_len]
        if np.sqrt(np.mean(chunk ** 2) + 1e-12) < threshold:
            silent_acc += len(chunk)
            if silent_acc <= max_samp:
                out.append(chunk)
        else:
            silent_acc = 0
            out.append(chunk)
    return np.concatenate(out) if out else arr

def _play_np(samples, sample_rate: int) -> None:
    sd.play(_to_numpy(samples), sample_rate)
    sd.wait()

def _play_audio_bytes(audio_bytes: bytes) -> None:
    import miniaudio
    decoded = miniaudio.decode(
        audio_bytes, output_format=miniaudio.SampleFormat.FLOAT32, nchannels=1
    )
    samples = np.array(decoded.samples, dtype=np.float32)
    sd.play(samples, decoded.sample_rate)
    sd.wait()

class EdgeTTSEngine:
    def __init__(self, voice: str = "en-US-GuyNeural"):
        self.voice = voice

    def speak(self, text: str, player) -> None:
        loop = asyncio.new_event_loop()
        try:
            audio_bytes = loop.run_until_complete(self._synth(text))
        finally:
            loop.close()
        if audio_bytes and not player.stop_requested:
            _play_audio_bytes(audio_bytes)

    async def _synth(self, text: str) -> bytes:
        import edge_tts
        comm = edge_tts.Communicate(text, self.voice)
        buf = bytearray()
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                buf.extend(chunk["data"])
        return bytes(buf)

_KOKORO_COMPAT_ERRORS = ("AlbertModel", "AutoModel", "cannot import name")

def _import_kokoro_pipeline():
    import sys
    def _try_import():
        from kokoro import KPipeline
        return KPipeline
    try:
        return _try_import()
    except Exception as first_err:
        err_msg = str(first_err)
        if not any(marker in err_msg for marker in _KOKORO_COMPAT_ERRORS):
            raise RuntimeError(f"Kokoro import failed: {first_err}\nRun: pip install kokoro>=0.9 soundfile") from first_err
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "kokoro>=0.9", "--upgrade", "--quiet", "--disable-pip-version-check"], capture_output=True)
        stale = [k for k in sys.modules if k == "kokoro" or k.startswith("kokoro.")]
        for key in stale: del sys.modules[key]
        try:
            return _try_import()
        except Exception as retry_err:
            raise RuntimeError(f"Kokoro still broken after upgrade: {retry_err}") from retry_err

_KOKORO_LANG_CODES = {"a": "a", "b": "b", "j": "j", "z": "z", "s": "s", "f": "f", "h": "h", "i": "i", "p": "p", "r": "r", "e": "e"}

class KokoroTTSEngine:
    def __init__(self, voice: str = "af_heart", speed: float = 1.0):
        self.voice = voice
        self.speed = speed
        self._pipeline = None
        self._lock = threading.Lock()
        self._init()

    @property
    def _lang_code(self) -> str:
        prefix = self.voice[0].lower() if self.voice else "a"
        return _KOKORO_LANG_CODES.get(prefix, "a")

    def _init(self) -> None:
        if self._pipeline is not None: return
        lang = self._lang_code
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            if device == "cpu":
                import os as _os
                torch.set_num_threads(max(1, min(4, (_os.cpu_count() or 4) // 2)))
        except Exception:
            device = "cpu"

        KPipeline = _import_kokoro_pipeline()
        def _create_pipeline():
            try: return KPipeline(lang_code=lang, device=device)
            except TypeError: return KPipeline(lang_code=lang)
        
        try:
            self._pipeline = _create_pipeline()
        except Exception as _first_err:
            _e = str(_first_err).lower()
            if any(k in _e for k in ("offline", "not found", "cache", "localentry", "does not exist", "outgoing", "local_files_only")):
                os.environ.pop("HF_HUB_OFFLINE", None)
                os.environ.pop("TRANSFORMERS_OFFLINE", None)
                os.environ.pop("HF_DATASETS_OFFLINE", None)
                try: self._pipeline = _create_pipeline()
                except Exception as _dl_err: raise RuntimeError(f"Kokoro model download failed: {_dl_err}") from _dl_err
            else: raise

        try:
            for _ in self._pipeline("hello", voice=self.voice, speed=self.speed): pass
        except Exception: pass

    def speak(self, text: str, player) -> None:
        with self._lock:
            if self._pipeline is None: self._init()
        audio_q = queue.Queue(maxsize=4)
        synth_error: list[Exception] = []

        def _synth():
            try:
                for _, _, audio in self._pipeline(text, voice=self.voice, speed=self.speed):
                    if player.stop_requested: break
                    if audio is not None:
                        arr = _compress_silence(_to_numpy(audio))
                        if arr.size > 0: audio_q.put(arr)
            except Exception as exc: synth_error.append(exc)
            finally: audio_q.put(None)

        synth_thread = threading.Thread(target=_synth, daemon=True)
        synth_thread.start()
        
        # Audio plays immediately as chunk 1 arrives while chunk 2 synthesizes in the background
        while not player.stop_requested:
            arr = audio_q.get()
            if arr is None or player.stop_requested: break
            _play_np(arr, 24000)
            
        synth_thread.join()
        if synth_error: raise synth_error[0]

class ElevenLabsTTSEngine:
    def __init__(self, api_key: str, voice_id: str = "pNInz6obpgDQGcFmaJgB"):
        self.api_key = api_key
        self.voice_id = voice_id

    def speak(self, text: str, player) -> None:
        import requests
        headers = {"xi-api-key": self.api_key, "Content-Type": "application/json"}
        payload = {"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
        resp = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}", json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        if not player.stop_requested:
            _play_audio_bytes(resp.content)

class TTSPlayer:
    def __init__(self, engine):
        self._engine = engine
        self._playing = False
        self._lock = threading.Lock()
        self.stop_requested = False

    def speak(self, text: str) -> None:
        try:
            with self._lock: 
                self._playing = True
                self.stop_requested = False
            self._engine.speak(text, self)
        except Exception as e: print(f"[TTS] Error: {e}")
        finally:
            with self._lock: self._playing = False

    def stop(self) -> None:
        with self._lock:
            self.stop_requested = True
        sd.stop()
        self._playing = False

def create_tts_player(config: dict) -> TTSPlayer:
    engine_name = config.get("tts_engine", "edgetts").lower()
    if engine_name == "kokoro":
        engine = KokoroTTSEngine(voice=config.get("tts_voice", "af_heart"), speed=float(config.get("tts_speed", 1.0)))
    elif engine_name == "elevenlabs":
        engine = ElevenLabsTTSEngine(api_key=config.get("elevenlabs_api_key", ""), voice_id=config.get("tts_voice", "pNInz6obpgDQGcFmaJgB"))
    else:
        engine = EdgeTTSEngine(voice=config.get("tts_voice", "en-US-GuyNeural"))
    return TTSPlayer(engine)

class TTSEngine:
    def __init__(self, config: ConfigManager, on_ai_audio_level: Optional[Callable[[float], None]] = None):
        self.config = config
        self.on_ai_audio_level = on_ai_audio_level
        self.speech_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.is_speaking = threading.Event()

        cfg_dict = {
            "tts_engine": self.config.get("tts_engine", "edgetts"),
            "tts_voice": self.config.get("tts_voice", "en-US-GuyNeural")
        }
        self.player = create_tts_player(cfg_dict)

        threading.Thread(target=self._worker, daemon=True).start()

    def bind_ai_level_callback(self, callback: Callable[[float], None]):
        self.on_ai_audio_level = callback

    def _emit_level(self, val: float):
        if self.on_ai_audio_level:
            try: self.on_ai_audio_level(val)
            except Exception: pass

    @staticmethod
    def clean_for_speech(text: str) -> str:
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        text = re.sub(r"[*_#`]", "", text)
        text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
        return text.strip()

    def speak(self, text: str):
        if self.config.get("quiet_mode", False): return
        cleaned = self.clean_for_speech(text)
        if cleaned:
            self.stop_event.clear()
            self.speech_queue.put(cleaned)

    def stop(self):
        self.stop_event.set()
        with self.speech_queue.mutex:
            self.speech_queue.queue.clear()
        self.speech_queue.put("__STOP__")
        self.player.stop()
        self._emit_level(0.0)

    def _worker(self):
        while True:
            text = self.speech_queue.get()
            if text == "__STOP__":
                self.player.stop()
                self.is_speaking.clear()
                self._emit_level(0.0)
                self.speech_queue.task_done()
                continue

            if text and not self.stop_event.is_set() and not self.config.get("quiet_mode", False):
                self.is_speaking.set()

                def _sim_levels():
                    t_start = time.time()
                    while self.is_speaking.is_set():
                        if self.stop_event.is_set(): break
                        elapsed = time.time() - t_start
                        wave = (0.48 + 0.28 * math.sin(elapsed * 16.5) + 0.18 * math.cos(elapsed * 9.2) + random.uniform(-0.06, 0.12))
                        self._emit_level(max(0.15, min(1.0, wave)))
                        time.sleep(0.03)

                threading.Thread(target=_sim_levels, daemon=True).start()

                try:
                    # Pass the full text block directly to the player.
                    # This leverages Kokoro's native thread pipeline and EdgeTTS batching.
                    self.player.speak(text)
                finally:
                    self.is_speaking.clear()
                    self._emit_level(0.0)
                    time.sleep(0.12)

            self.speech_queue.task_done()