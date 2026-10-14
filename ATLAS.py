import os
import time
import threading
import queue
import webview
import mss
import re
import base64
from PIL import Image
import speech_recognition as sr
import win32com.client
import pythoncom
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY is not set in the .env file.")

MODEL_ID = "gemini-3.1-flash-lite"
client = genai.Client(api_key=API_KEY)

# Thread-safe Speech Queue and Interruption Event
speech_queue = queue.Queue()
stop_speaking = threading.Event()

def clean_for_speech(text):
    """Removes Markdown symbols so the voice engine reads naturally."""
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL) 
    text = re.sub(r'[*_#`]', '', text) 
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text) 
    return text.strip()

def tts_worker():
    """Background worker using native Windows SAPI5 with bilingual voice switching."""
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

    speaker.Voice = george_voice or default_voice or voices.Item(0)

    while True:
        text = speech_queue.get()
        
        if text == "__STOP__":
            speaker.Speak("", 2) 
            speech_queue.task_done()
            continue

        if text and not stop_speaking.is_set():
            is_hindi = bool(re.search(r'[\u0900-\u097F]', text))
            
            if is_hindi and hemant_voice:
                speaker.Voice = hemant_voice
            elif not is_hindi and george_voice:
                speaker.Voice = george_voice
            elif not is_hindi and default_voice:
                speaker.Voice = default_voice
                
            sentences = re.split(r'(?<=[.!?]) +', text)
            for sentence in sentences:
                if stop_speaking.is_set():
                    speaker.Speak("", 2) 
                    break 
                if sentence.strip():
                    speaker.Speak(sentence.strip(), 1) 
                    
                    while speaker.Status.RunningState == 2: 
                        if stop_speaking.is_set():
                            speaker.Speak("", 2) 
                            break
                        time.sleep(0.05)
                        
        speech_queue.task_done()

threading.Thread(target=tts_worker, daemon=True).start()

class AtlasBackend:
    def __init__(self):
        self.is_pinned = False
        self.window = None
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 0.5 
        self.recognizer.non_speaking_duration = 0.4
        self.is_processing = False
        self._initialize_chat()

    def _initialize_chat(self):
        """Creates or resets the Gemini chat session."""
        self.chat_session = client.chats.create(
            model=MODEL_ID,
            config=types.GenerateContentConfig(
                system_instruction="Respond in 2-3 short sentences by default. Use markdown for lists or code if asked."
            )
        )

    def set_window(self, window):
        self.window = window

    def stop_audio(self):
        """Safely stops TTS and clears the queue."""
        stop_speaking.set()
        with speech_queue.mutex:
            speech_queue.queue.clear()
        speech_queue.put("__STOP__")

    def speak(self, text):
        """Pushes text to the TTS worker queue."""
        speech_queue.put(text)

    
    def toggle_pin(self, pinned):
        import ctypes
        from ctypes import wintypes
    
        user32 = ctypes.WinDLL("user32", use_last_error=True)
    
        user32.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT
        ]
        user32.SetWindowPos.restype = wintypes.BOOL
    
        user32.GetWindowLongW.argtypes = [
            wintypes.HWND,
            ctypes.c_int
        ]
        user32.GetWindowLongW.restype = ctypes.c_long
    
        # Find the ATLAS native window handle.
        hwnd = None
    
        try:
            native = self.window.native if self.window else None
            handle = getattr(native, "Handle", None)
    
            if handle:
                hwnd = wintypes.HWND(int(handle))
        except Exception:
            pass
    
        # Fallback: find the window by its title.
        if not hwnd:
            user32.FindWindowW.argtypes = [
                wintypes.LPCWSTR,
                wintypes.LPCWSTR
            ]
            user32.FindWindowW.restype = wintypes.HWND
    
            hwnd = user32.FindWindowW(
                None,
                "ATLAS AI Assistant"
            )
    
        if not hwnd:
            return False
    
        HWND_TOPMOST = wintypes.HWND(-1)
        HWND_NOTOPMOST = wintypes.HWND(-2)
    
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOACTIVATE = 0x0010
    
        GWL_EXSTYLE = -20
        WS_EX_TOPMOST = 0x00000008
    
        # Apply the requested always-on-top state.
        ctypes.set_last_error(0)
    
        success = user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST if pinned else HWND_NOTOPMOST,
            0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        )
    
        if not success:
            return False
    
        # Verify the actual Windows window state.
        style = user32.GetWindowLongW(
            hwnd,
            GWL_EXSTYLE
        )
    
        actual_state = bool(style & WS_EX_TOPMOST)
    
        self.is_pinned = actual_state
    
        return actual_state == bool(pinned)


    def clear_chat(self):
        """Wipes the internal session memory."""
        self._initialize_chat()

    def capture_screen(self, output_path="current_screen.png"):
        """Captures screen. Hides ATLAS UI temporarily to prevent self-capture."""
        if self.window:
            self.window.hide()
            time.sleep(0.15)  # Give Windows Desktop Manager time to redraw background
            
        with mss.MSS() as sct:
            sct.shot(mon=1, output=output_path)
            
        if self.window:
            self.window.show()
            
        img = Image.open(output_path)
        img.thumbnail((1280, 1280))
        img.save(output_path)
        
        # Send thumbnail preview to UI
        with open(output_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            self.window.evaluate_js(f"window.showImagePreview('data:image/png;base64,{encoded_string}')")
            
        return output_path

    def _stream_gemini(self, contents):
        """Streams Gemini responses using persistent memory and chat bubbles."""
        full_text = ""
        try:
            self.window.evaluate_js("window.createNewAssistantBubble()")
            response = self.chat_session.send_message_stream(contents)

            for chunk in response:
                if chunk.text:
                    full_text += chunk.text
                    safe_chunk = chunk.text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("`", "\\`")
                    self.window.evaluate_js(f"window.appendChunk('{safe_chunk}')")

            self.window.evaluate_js("window.finalizeResponse()")
            
            if full_text.strip():
                clean_text = clean_for_speech(full_text)
                self.speak(clean_text)

        except Exception as e:
            err_msg = f"Error: {e}"
            self.window.evaluate_js(f"window.appendChunk('{err_msg.replace('\'', '\\\'')}')")
            self.window.evaluate_js("window.finalizeResponse()")

    def ask_with_screen(self, question):
        if self.is_processing: return
        self.is_processing = True
        try:
            img_path = self.capture_screen()
            self._stream_gemini([question, Image.open(img_path)])
        finally:
            self.is_processing = False

    def ask_text_only(self, question):
        if self.is_processing: return
        self.is_processing = True
        try:
            self._stream_gemini([question])
        finally:
            self.is_processing = False

    def trigger_manual_voice(self):
        if self.is_processing: return
        threading.Thread(target=self._listen_and_execute, daemon=True).start()

    def _listen_and_execute(self):
        self.is_processing = True
        self.stop_audio()
        time.sleep(0.2)
        stop_speaking.clear()
        
        try:
            with sr.Microphone() as source:
                self.recognizer.pause_threshold = 0.5
                self.recognizer.non_speaking_duration = 0.3
                self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=12) 
                
            self.window.evaluate_js("setStatus('Transcribing...', '#f59e0b', true)")
            transcript = self.recognizer.recognize_google(audio)

            if transcript:
                safe_tr = transcript.replace("'", "\\'")
                self.window.evaluate_js(f"window.updateInputBox('{safe_tr}')")
                
                # Append user bubble for voice input
                self.window.evaluate_js(f"window.addUserBubble('🎙️ {safe_tr}')")
                
                if "screen" in transcript.lower():
                    self.window.evaluate_js("setStatus('Analyzing screen...', '#06b6d4', true)")
                    img_path = self.capture_screen()
                    self._stream_gemini([transcript, Image.open(img_path)])
                else:
                    self.window.evaluate_js("setStatus('Thinking...', '#f59e0b', true)")
                    self._stream_gemini([transcript])
        except sr.UnknownValueError:
            self.window.evaluate_js("setStatus('Could not understand voice.', '#ef4444', false)")
        except Exception as e:
            self.window.evaluate_js(f"window.appendChunk('Voice Error: {e}')")
            self.window.evaluate_js("window.finalizeResponse()")
        finally:
            self.is_processing = False
            self.window.evaluate_js("setStatus('Ready', '#10b981', false)")


def wake_word_listener(backend):
    """Background thread listening for 'Atlas'."""
    r = sr.Recognizer()
    r.pause_threshold = 0.5 
    r.non_speaking_duration = 0.3
    r.energy_threshold = 300
    r.dynamic_energy_threshold = False

    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source, duration=1.0)
        
        while True:
            try:
                audio = r.listen(source, phrase_time_limit=5)
                
                if backend.is_processing:
                    continue

                phrase = r.recognize_google(audio).lower()

                if "atlas" in phrase:
                    backend.stop_audio()
                    time.sleep(0.1) 
                    stop_speaking.clear() 
                    
                    backend.is_processing = True 
                    try:
                        command = phrase.replace("atlas", "").strip()
                        
                        if not command:
                            backend.window.evaluate_js("setStatus('Atlas detected! Listening...', '#ef4444', true)")
                            r.pause_threshold = 0.5 
                            r.non_speaking_duration = 0.3
                            cmd_audio = r.listen(source, timeout=4, phrase_time_limit=10)
                            backend.window.evaluate_js("setStatus('Processing voice...', '#f59e0b', true)")
                            command = r.recognize_google(cmd_audio).lower()

                        if command:
                            safe_cmd = command.replace("'", "\\'")
                            backend.window.evaluate_js(f"window.updateInputBox('{safe_cmd}')")

                            if "explain screen" in command or "screen" in command:
                                backend.window.evaluate_js(f"window.addUserBubble('🎙️ 🖥️ [Screen]: {safe_cmd}')")
                                backend.window.evaluate_js("setStatus('Inspecting screen...', '#06b6d4', true)")
                                img_path = backend.capture_screen()
                                backend._stream_gemini([command, Image.open(img_path)])
                            else:
                                backend.window.evaluate_js(f"window.addUserBubble('🎙️ {safe_cmd}')")
                                backend.window.evaluate_js("setStatus('Thinking...', '#f59e0b', true)")
                                backend._stream_gemini([command])
                    finally:
                        backend.is_processing = False
                        backend.window.evaluate_js("setStatus('Ready', '#10b981', false)")
                        
            except (sr.WaitTimeoutError, sr.UnknownValueError, Exception):
                pass 

if __name__ == '__main__':
    backend = AtlasBackend()
    
    window = webview.create_window(
        'ATLAS AI Assistant',
        'ui/index.html',
        js_api=backend,
        width=580,
        height=720,
        resizable=True
    )
    backend.set_window(window)

    threading.Thread(target=wake_word_listener, args=(backend,), daemon=True).start()

    webview.start()