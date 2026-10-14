import os
import time
import threading
import queue
import webview
import mss
import re
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
    """Background worker using native Windows SAPI5 to bypass pyttsx3 crashes."""
    pythoncom.CoInitialize()
    speaker = win32com.client.Dispatch("SAPI.SpVoice")
    
    # TITAN VOICE: Rate ranges from -10 to 10. -2 creates a deep, methodical sound.
    speaker.Rate = -2 
    speaker.Volume = 100
    
    # Force a male voice if available (Looks for Microsoft David)
    voices = speaker.GetVoices()
    for i in range(voices.Count):
        voice = voices.Item(i)
        if "david" in voice.GetDescription().lower() or "male" in voice.GetDescription().lower():
            speaker.Voice = voice
            break

    while True:
        text = speech_queue.get()
        
        if text == "__STOP__":
            # 2 = SVSFPurgeBeforeSpeak (Instantly cuts off current speech)
            speaker.Speak("", 2) 
            speech_queue.task_done()
            continue

        if text and not stop_speaking.is_set():
            sentences = re.split(r'(?<=[.!?]) +', text)
            for sentence in sentences:
                if stop_speaking.is_set():
                    speaker.Speak("", 2) 
                    break 
                if sentence.strip():
                    # 1 = SVSFlagsAsync (Speak asynchronously so we can monitor for interruptions)
                    speaker.Speak(sentence.strip(), 1) 
                    
                    # Loop while speaking to check for instant interruption
                    while speaker.Status.RunningState == 2: 
                        if stop_speaking.is_set():
                            speaker.Speak("", 2) # Instantly cut off audio mid-word
                            break
                        time.sleep(0.05)
                        
        speech_queue.task_done()

threading.Thread(target=tts_worker, daemon=True).start()

class AtlasBackend:
    def __init__(self):
        self.window = None
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 1.5
        self.is_processing = False
        
        # Initialize persistent memory and system instructions
        self.chat_session = client.chats.create(
            model=MODEL_ID,
            config=types.GenerateContentConfig(
                system_instruction="Respond in 2-3 short sentences by default. Provide longer answers only if explicitly asked."
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
        speech_queue.put(text)

    def capture_screen(self, output_path="current_screen.png"):
        with mss.MSS() as sct:
            sct.shot(mon=1, output=output_path)
        img = Image.open(output_path)
        img.thumbnail((1280, 1280))
        img.save(output_path)
        return output_path

    def _stream_gemini(self, contents):
        """Streams Gemini responses using persistent memory."""
        full_text = ""
        try:
            self.window.evaluate_js("window.clearResponse()")
            
            # Send message to the ongoing chat session instead of isolated generation
            response = self.chat_session.send_message_stream(contents)

            for chunk in response:
                if chunk.text:
                    full_text += chunk.text
                    safe_chunk = chunk.text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
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
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=15) 
                
            self.window.evaluate_js("setStatus('Transcribing...', '#f59e0b', true)")
            transcript = self.recognizer.recognize_google(audio)

            if transcript:
                safe_tr = transcript.replace("'", "\\'")
                self.window.evaluate_js(f"window.updateInputBox('{safe_tr}')")
                
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
        finally:
            self.is_processing = False
            self.window.evaluate_js("setStatus('Ready', '#10b981', false)")


def wake_word_listener(backend):
    """Background thread listening for 'Atlas' with continuous audio streaming."""
    r = sr.Recognizer()
    r.pause_threshold = 0.6 
    r.energy_threshold = 400
    r.dynamic_energy_threshold = True

    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source, duration=1.0)
        
        while True:
            try:
                audio = r.listen(source, phrase_time_limit=8)
                
                if backend.is_processing:
                    continue

                phrase = r.recognize_google(audio).lower()

                if "atlas" in phrase:
                    backend.stop_audio()
                    time.sleep(0.1) 
                    stop_speaking.clear() 
                    
                    backend.is_processing = True 
                    try:
                        backend.window.evaluate_js("setStatus('Atlas detected! Listening...', '#ef4444', true)")
                        
                        command = phrase.replace("atlas", "").strip()
                        
                        if not command:
                            r.pause_threshold = 1.5 
                            cmd_audio = r.listen(source, timeout=4, phrase_time_limit=10)
                            command = r.recognize_google(cmd_audio).lower()
                            r.pause_threshold = 0.6 

                        if command:
                            safe_cmd = command.replace("'", "\\'")
                            backend.window.evaluate_js(f"window.updateInputBox('{safe_cmd}')")

                            if "explain screen" in command or "screen" in command:
                                backend.window.evaluate_js("setStatus('Inspecting screen...', '#06b6d4', true)")
                                img_path = backend.capture_screen()
                                backend._stream_gemini([command, Image.open(img_path)])
                            else:
                                backend.window.evaluate_js("setStatus('Thinking...', '#f59e0b', true)")
                                backend._stream_gemini([command])
                    finally:
                        backend.is_processing = False
                        backend.window.evaluate_js("setStatus('Ready', '#10b981', false)")
                        
            except sr.WaitTimeoutError:
                pass 
            except sr.UnknownValueError:
                pass 
            except Exception:
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