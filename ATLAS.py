import os
import time
import threading
import queue
import webview
import mss
import re
import base64
import subprocess
import json
import urllib.request
import urllib.parse
from datetime import datetime
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

speech_queue = queue.Queue()
stop_speaking = threading.Event()

# Global reference to push UI updates
global_backend = None

# ==========================================
# ATLAS TOOL REGISTRY & MEMORY
# ==========================================
WORKSPACE_DIR = os.path.join(os.getcwd(), "ATLAS_Workspace")
TASKS_FILE = os.path.join(WORKSPACE_DIR, "tasks.json")
os.makedirs(WORKSPACE_DIR, exist_ok=True)

def _load_tasks():
    if not os.path.exists(TASKS_FILE): return []
    try:
        with open(TASKS_FILE, 'r', encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def _save_tasks(tasks):
    with open(TASKS_FILE, 'w', encoding="utf-8") as f:
        json.dump(tasks, f, indent=4)
        
    # Instantly sync UI with the latest tasks
    if global_backend and global_backend.window:
        try:
            active_tasks = [t for t in tasks if not t.get("notified")]
            json_str = json.dumps(active_tasks)
            b64_str = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
            global_backend.window.evaluate_js(f"window.renderTasksFromBase64('{b64_str}')")
        except Exception as e:
            print(f"UI Sync Error: {e}")

# --- Phase 1 & 2: Safe Local Tools ---
def create_note(filename: str, content: str) -> str:
    safe_filename = "".join([c for c in filename if c.isalpha() or c.isdigit() or c in " ._-"]).rstrip()
    filepath = os.path.join(WORKSPACE_DIR, safe_filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f: f.write(content)
        return f"SUCCESS: Note saved at {filepath}"
    except Exception as e: return f"FAILED: Error saving note - {str(e)}"

def read_document(filename: str) -> str:
    filepath = os.path.join(WORKSPACE_DIR, filename)
    if not os.path.exists(filepath): return "FAILED: File does not exist."
    try:
        with open(filepath, "r", encoding="utf-8") as f: return f.read()
    except Exception as e: return f"FAILED: Error reading file - {str(e)}"

def search_files(keyword: str) -> str:
    files = os.listdir(WORKSPACE_DIR)
    matches = [f for f in files if keyword.lower() in f.lower() and os.path.isfile(os.path.join(WORKSPACE_DIR, f))]
    if not matches: return f"No files found matching '{keyword}'."
    return f"Found files: {', '.join(matches)}"

def open_application(app_name: str) -> str:
    allowed_apps = {"notepad": "notepad.exe", "calculator": "calc.exe", "browser": "start msedge"}
    if app_name.lower() not in allowed_apps: return f"FAILED: '{app_name}' is not approved."
    try:
        subprocess.Popen(allowed_apps[app_name.lower()], shell=True)
        return f"SUCCESS: Launched {app_name}."
    except Exception as e: return f"FAILED: {str(e)}"

def get_current_time() -> str:
    return datetime.now().strftime("%A, %B %d, %Y - %H:%M")

# --- Phase 3: Tasks & Reminders ---
def create_task(title: str, due_time_str: str) -> str:
    try:
        datetime.strptime(due_time_str, "%Y-%m-%d %H:%M")
        tasks = _load_tasks()
        task_id = max([t["id"] for t in tasks] + [0]) + 1
        tasks.append({"id": task_id, "title": title, "due_time": due_time_str, "notified": False})
        _save_tasks(tasks) # Triggers UI Update
        return f"SUCCESS: Task #{task_id} scheduled for {due_time_str}."
    except ValueError: return "FAILED: Invalid time format. Must be 'YYYY-MM-DD HH:MM'."

def list_tasks() -> str:
    tasks = [t for t in _load_tasks() if not t.get("notified")]
    if not tasks: return "No pending tasks."
    return "\n".join([f"ID {t['id']}: {t['title']} at {t['due_time']}" for t in tasks])

def cancel_task(task_id: int) -> str:
    tasks = _load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["notified"] = True
            _save_tasks(tasks) # Triggers UI Update
            return f"SUCCESS: Task {task_id} completed/cancelled."
    return f"FAILED: Task ID {task_id} not found."

def search_wikipedia(query: str) -> str:
    try:
        safe_query = urllib.parse.quote(query)
        url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={safe_query}&utf8=&format=json"
        req = urllib.request.Request(url, headers={'User-Agent': 'ATLAS_AI/1.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            results = data.get('query', {}).get('search', [])
            if not results: return f"No results found for '{query}'."
            clean_snippet = re.sub(r'<[^>]+>', '', results[0]['snippet'])
            return f"Source: Wikipedia ({results[0]['title']})\nSummary: {clean_snippet}..."
    except Exception as e: return f"FAILED: Web search error - {str(e)}"

ATLAS_TOOLS = [create_note, read_document, search_files, open_application, get_current_time, create_task, list_tasks, cancel_task, search_wikipedia]

def clean_for_speech(text):
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL) 
    text = re.sub(r'[*_#`]', '', text) 
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text) 
    return text.strip()

def tts_worker():
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
        if "george" in desc: george_voice = voices.Item(i)
        elif "hemant" in desc: hemant_voice = voices.Item(i)
        elif "david" in desc: default_voice = voices.Item(i)

    speaker.Voice = george_voice or default_voice or voices.Item(0)

    while True:
        text = speech_queue.get()
        if text == "__STOP__":
            speaker.Speak("", 2) 
            speech_queue.task_done()
            continue

        if text and not stop_speaking.is_set():
            is_hindi = bool(re.search(r'[\u0900-\u097F]', text))
            if is_hindi and hemant_voice: speaker.Voice = hemant_voice
            elif not is_hindi and george_voice: speaker.Voice = george_voice
            elif not is_hindi and default_voice: speaker.Voice = default_voice
                
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

def reminder_worker(backend):
    while True:
        time.sleep(15) 
        tasks = _load_tasks()
        changed = False
        now = datetime.now()
        
        for t in tasks:
            if not t.get("notified"):
                try:
                    due = datetime.strptime(t["due_time"], "%Y-%m-%d %H:%M")
                    if now >= due:
                        t["notified"] = True
                        changed = True
                        
                        msg = f"🔔 **Reminder:** {t['title']}"
                        if backend.window:
                            backend.window.evaluate_js("window.createNewAssistantBubble()")
                            backend.window.evaluate_js(f"window.appendChunk('{msg}')")
                            backend.window.evaluate_js("window.finalizeResponse()")
                            backend.speak(f"Reminder: {t['title']}")
                except: pass 
        if changed:
            _save_tasks(tasks) # Triggers UI Update

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
        self.chat_session = client.chats.create(
            model=MODEL_ID,
            config=types.GenerateContentConfig(
                system_instruction="""You are ATLAS, a personal AI desktop assistant. 
                You have access to tools to interact with the user's system and memory. 
                Before setting a reminder, ALWAYS check the current time. 
                Always confirm what action you took in 1-2 concise sentences.""",
                tools=ATLAS_TOOLS,
                temperature=0.3
            )
        )

    def set_window(self, window):
        self.window = window

    # --- UI Callable Endpoints for Tasks ---
    def get_ui_tasks_b64(self):
        """Called by UI on startup to get the initial list."""
        active_tasks = [t for t in _load_tasks() if not t.get("notified")]
        json_str = json.dumps(active_tasks)
        return base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

    def ui_cancel_task(self, task_id):
        """Called directly by the UI when the user clicks 'Done'."""
        cancel_task(int(task_id))

    def stop_audio(self):
        stop_speaking.set()
        with speech_queue.mutex: speech_queue.queue.clear()
        speech_queue.put("__STOP__")

    def speak(self, text):
        speech_queue.put(text)

    def toggle_pin(self, pinned):
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.SetWindowPos.restype = wintypes.BOOL
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_long
        
        hwnd = None
        try:
            native = self.window.native if self.window else None
            handle = getattr(native, "Handle", None)
            if handle: hwnd = wintypes.HWND(int(handle))
        except Exception: pass
            
        if not hwnd:
            user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
            user32.FindWindowW.restype = wintypes.HWND
            hwnd = user32.FindWindowW(None, "ATLAS AI Assistant")
            
        if not hwnd: return False
        
        HWND_TOPMOST = wintypes.HWND(-1)
        HWND_NOTOPMOST = wintypes.HWND(-2)
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOACTIVATE = 0x0010
        GWL_EXSTYLE = -20
        WS_EX_TOPMOST = 0x00000008
        
        ctypes.set_last_error(0)
        success = user32.SetWindowPos(hwnd, HWND_TOPMOST if pinned else HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        if not success: return False
        
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        actual_state = bool(style & WS_EX_TOPMOST)
        self.is_pinned = actual_state
        return actual_state == bool(pinned)

    def clear_chat(self):
        self._initialize_chat()

    def capture_screen(self, output_path="current_screen.png"):
        if self.window:
            self.window.hide()
            time.sleep(0.15) 
            
        with mss.MSS() as sct:
            sct.shot(mon=1, output=output_path)
            
        if self.window:
            self.window.show()
            
        img = Image.open(output_path)
        img.thumbnail((1280, 1280))
        img.save(output_path)
        
        with open(output_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            self.window.evaluate_js(f"window.showImagePreview('data:image/png;base64,{encoded_string}')")
            
        return output_path

    def _execute_gemini(self, contents):
        try:
            self.window.evaluate_js("window.createNewAssistantBubble()")
            response = self.chat_session.send_message(contents)
            
            if response.text:
                safe_text = response.text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("`", "\\`")
                self.window.evaluate_js(f"window.appendChunk('{safe_text}')")
                
                clean_text = clean_for_speech(response.text)
                self.speak(clean_text)

            self.window.evaluate_js("window.finalizeResponse()")

        except Exception as e:
            err_msg = f"Error: {e}"
            self.window.evaluate_js(f"window.appendChunk('{err_msg.replace('\'', '\\\'')}')")
            self.window.evaluate_js("window.finalizeResponse()")

    def ask_with_screen(self, question):
        if self.is_processing: return
        self.is_processing = True
        try:
            img_path = self.capture_screen()
            self._execute_gemini([question, Image.open(img_path)])
        finally:
            self.is_processing = False

    def ask_text_only(self, question):
        if self.is_processing: return
        self.is_processing = True
        try:
            self._execute_gemini([question])
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
                self.window.evaluate_js(f"window.addUserBubble('🎙️ {safe_tr}')")
                
                if "screen" in transcript.lower():
                    self.window.evaluate_js("setStatus('Analyzing screen...', '#06b6d4', true)")
                    img_path = self.capture_screen()
                    self._execute_gemini([transcript, Image.open(img_path)])
                else:
                    self.window.evaluate_js("setStatus('Thinking...', '#f59e0b', true)")
                    self._execute_gemini([transcript])
        except sr.UnknownValueError:
            self.window.evaluate_js("setStatus('Could not understand voice.', '#ef4444', false)")
        except Exception as e:
            self.window.evaluate_js(f"window.appendChunk('Voice Error: {e}')")
            self.window.evaluate_js("window.finalizeResponse()")
        finally:
            self.is_processing = False
            self.window.evaluate_js("setStatus('Ready', '#10b981', false)")

def wake_word_listener(backend):
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
                if backend.is_processing: continue
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
                                backend._execute_gemini([command, Image.open(img_path)])
                            else:
                                backend.window.evaluate_js(f"window.addUserBubble('🎙️ {safe_cmd}')")
                                backend.window.evaluate_js("setStatus('Thinking...', '#f59e0b', true)")
                                backend._execute_gemini([command])
                    finally:
                        backend.is_processing = False
                        backend.window.evaluate_js("setStatus('Ready', '#10b981', false)")
                        
            except (sr.WaitTimeoutError, sr.UnknownValueError, Exception):
                pass 

if __name__ == '__main__':
    backend = AtlasBackend()
    global_backend = backend # Bind for UI pushes
    
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
    threading.Thread(target=reminder_worker, args=(backend,), daemon=True).start()
    
    webview.start()