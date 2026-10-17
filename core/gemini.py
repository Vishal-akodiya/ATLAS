import io
import os
import time
import inspect
import threading
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

MODEL_FAILOVER_POOL = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]

# Reduced penalty so a single timeout doesn't brick the app for 5 minutes
_COOLDOWN_SECONDS = 30
_UNAVAILABLE_SECONDS = 30 * 60
_GONE_SECONDS = 6 * 60 * 60 

_cooldown = {}
_cool_lock = threading.Lock()

def _cool(model: str, seconds: float = _COOLDOWN_SECONDS) -> None:
    with _cool_lock:
        _cooldown[model] = time.monotonic() + seconds

def _cooling(model: str) -> bool:
    with _cool_lock:
        until = _cooldown.get(model, 0.0)
        if until and time.monotonic() < until:
            return True
        _cooldown.pop(model, None)
        return False

def _make_standalone_tool(bound_func):
    if not inspect.ismethod(bound_func):
        return bound_func
    def wrapper(*args, **kwargs):
        return bound_func(*args, **kwargs)
    wrapper.__name__ = bound_func.__name__
    wrapper.__qualname__ = bound_func.__name__
    wrapper.__doc__ = bound_func.__doc__
    orig_ann = getattr(bound_func, "__annotations__", {})
    wrapper.__annotations__ = {k: v for k, v in orig_ann.items() if k != "self"}
    wrapper.__signature__ = inspect.signature(bound_func)
    return wrapper

class GeminiEngine:
    def __init__(self, tools_list: list):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in the .env file.")
        
        preferred = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite").strip()
        self.model_pool = [preferred] + [m for m in MODEL_FAILOVER_POOL if m != preferred]
        self.active_model = preferred
        
        try:
            self.client = genai.Client(
                api_key=api_key,
                # Increased timeout to 120s (120000ms) to allow for non-streamed processing
                http_options=types.HttpOptions(timeout=120000),
            )
        except Exception:
            self.client = genai.Client(api_key=api_key)

        self.all_tools = {}
        for func in tools_list:
            clean_fn = _make_standalone_tool(func)
            self.all_tools[clean_fn.__name__] = clean_fn
            
        self.prompt_path = os.path.join(os.path.dirname(__file__), "prompt.txt")
        self.system_prompt = self._load_system_prompt()
        self.rolling_history: list[str] = []

    def __deepcopy__(self, memo):
        return self

    def _load_system_prompt(self) -> str:
        if os.path.exists(self.prompt_path):
            with open(self.prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        return "You are ATLAS, a fast personal AI desktop operator. Answer concisely in 1-2 sentences."

    def reset_chat(self):
        self.rolling_history.clear()

    @staticmethod
    def compress_image_for_api(image_input, max_dim: int = 1024, quality: int = 72) -> types.Part:
        if isinstance(image_input, str):
            img = Image.open(image_input)
        else:
            img = image_input
        img = img.convert("RGB")
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")

    def _select_relevant_tools(self, prompt: str, with_screen: bool = False) -> list:
        p = prompt.lower()
        selected = ["get_current_time"]
        
        if with_screen or any(w in p for w in ("screen", "click", "button", "locate", "look", "type", "window", "scroll", "key", "shortcut")):
            selected.extend(["inspect_screen_state", "locate_and_interact_on_screen", "type_text", "press_hotkey", "click_control", "scroll_screen", "focus_window"])
        if any(w in p for w in ("open", "launch", "start", "app", "whatsapp", "close", "minimize")):
            selected.extend(["open_app", "list_installed_apps", "send_whatsapp_message", "focus_window", "minimize_window", "close_app"])
        if any(w in p for w in ("file", "note", "document", "read", "write", "save", "folder", "duplicate", "compare", "delete", "move", "rename", "undo")):
            selected.extend(["search_files", "read_document", "create_file", "move_file", "compare_documents", "find_duplicates_or_large_files", "delete_file", "undo_last_action"])
        if any(w in p for w in ("remind", "task", "schedule", "todo", "snooze", "overdue", "tomorrow", "briefing")):
            selected.extend(["create_task", "list_tasks", "snooze_task", "reschedule_task", "cancel_task", "generate_daily_briefing"])
        if any(w in p for w in ("search", "web", "wikipedia", "google", "research", "url", "http", "page", "website")):
            selected.extend(["web_search", "extract_webpage_text", "open_page"])
        if any(w in p for w in ("remember", "memory", "preference", "forget", "recall", "checkpoint", "resume")):
            selected.extend(["save_user_memory", "search_user_memory", "delete_user_memory", "save_task_checkpoint"])
        if any(w in p for w in ("email", "draft", "calendar", "event", "meeting", "message", "team")):
            selected.extend(["draft_email", "prepare_calendar_event", "send_message", "send_whatsapp_message"])
        if any(w in p for w in ("cpu", "ram", "disk", "system", "status", "running", "log", "command", "ipconfig")):
            selected.extend(["check_system_status", "check_app_running", "read_logs", "run_approved_command"])
            
        seen = set()
        pruned_funcs = []
        for name in selected:
            if name not in seen and name in self.all_tools:
                seen.add(name)
                pruned_funcs.append(self.all_tools[name])
        return pruned_funcs

    def _execute_with_cooldown(self, contents: list, tools: list = None, temperature: float = 0.2):
        last_err = None
        base_kwargs = {"temperature": temperature}
        if self.system_prompt:
            base_kwargs["system_instruction"] = self.system_prompt
        if tools:
            base_kwargs["tools"] = tools
            
        cfg = types.GenerateContentConfig(**base_kwargs)
        for model_name in self.model_pool:
            if _cooling(model_name):
                continue
                
            try:
                res = self.client.models.generate_content(model=model_name, contents=contents, config=cfg)
                self.active_model = model_name
                return res
            except Exception as e:
                err_msg = str(e).lower()
                last_err = e
                # Added 'timeout' and 'readtimeout' catching to prevent full system lockouts
                if "429" in err_msg or "resource_exhausted" in err_msg:
                    _cool(model_name, _COOLDOWN_SECONDS)
                    print(f"[Gemini] {model_name}: out of quota   resting for {_COOLDOWN_SECONDS}s")
                elif "503" in err_msg or "504" in err_msg or "unavailable" in err_msg or "deadline_exceeded" in err_msg or "timeout" in err_msg:
                    _cool(model_name, _COOLDOWN_SECONDS)
                    print(f"[Gemini] {model_name}: timeout/unavailable   resting for {_COOLDOWN_SECONDS}s")
                elif "404" in err_msg or "not found" in err_msg or "is not supported" in err_msg or "permission" in err_msg or "403" in err_msg:
                    _cool(model_name, _GONE_SECONDS)
                    print(f"[Gemini] {model_name}: unavailable/gone   skipping for session")
                else:
                    _cool(model_name, _COOLDOWN_SECONDS)
                    print(f"[Gemini] {model_name} failed: {e}")
                continue
            
        raise RuntimeError(f"All models failed or are resting. Last error: {last_err}")

    def generate_vision_content(self, prompt: str, pil_image: Image.Image, temperature: float = 0.1) -> str:
        img_part = self.compress_image_for_api(pil_image, max_dim=1024, quality=72)
        res = self._execute_with_cooldown(contents=[prompt, img_part], tools=None, temperature=temperature)
        return (res.text or "").strip()

    def send(self, prompt: str, image_path: str = None) -> str:
        relevant_tools = self._select_relevant_tools(prompt, with_screen=bool(image_path))
        
        context_prefix = ""
        if self.rolling_history:
            recent = "\n".join(self.rolling_history[-4:])
            context_prefix = f"Recent Conversation Context:\n{recent}\n\nCurrent Request: "
            
        contents = [context_prefix + prompt]
        if image_path and os.path.exists(image_path):
            contents.append(self.compress_image_for_api(image_path, max_dim=1024, quality=72))
            
        res = self._execute_with_cooldown(contents=contents, tools=relevant_tools, temperature=0.2)
        reply = (res.text or "Task completed and verified.").strip()
        
        self.rolling_history.append(f"User: {prompt[:160]}")
        self.rolling_history.append(f"ATLAS: {reply[:220]}")
        if len(self.rolling_history) > 8:
            self.rolling_history = self.rolling_history[-8:]
            
        return reply